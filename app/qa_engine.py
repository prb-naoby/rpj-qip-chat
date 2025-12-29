from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, List


import pandas as pd
from pandas import DataFrame
from openai import OpenAI

from .settings import AppSettings
from app.logger import get_chat_logger

settings = AppSettings()
logger = get_chat_logger()


@dataclass
class QAResult:
    prompt: str
    response: Any
    code: str | None = None
    explanation: str | None = None  # AI explanation of the results
    ui_components: List[dict] = field(default_factory=list)  # Native UI components to render
    iterations_used: int = 1  # How many iterations to get valid result
    has_error: bool = False  # True if generation failed (all iterations failed)
    failed_code: str = ""  # Store the failed code for debugging
    validation_notes: List[str] = field(default_factory=list)  # Validation feedback


_SYSTEM_PROMPT = """\
Kamu adalah asisten analisis data Python yang berjalan di dalam environment Python standard.
Data ini berasal dari konteks manufaktur/pabrik - semua kolom berhubungan dengan produksi, kualitas, dan performa.


## KRITIS - BACA INI DULU!
Variable `df` SUDAH BERISI DATA LENGKAP ({total_rows} baris) yang di-load dari parquet.
JANGAN PERNAH membuat DataFrame baru! Langsung gunakan `df`.

## Kolom yang Tersedia
{columns}

## Sample Data
```
{sample}
```

## Aturan Output - PRIORITAS UTAMA!
Jawab dengan PENJELASAN NATURAL yang bersih. Hindari output teknis/debug.

1. **UTAMAKAN print() untuk penjelasan**: Jawab pertanyaan user dengan bahasa natural dan LANGSUNG ke inti.
   - ❌ SALAH: print(f"Line dengan rata-rata pct_rft tertinggi: ['Line 14']")
   - ✅ BENAR: print("Line 14 memiliki rata-rata RFT tertinggi sebesar 91%.")

2. **MINIMAL display()**: Gunakan display() HANYA JIKA data tabel DIPERLUKAN untuk menjawab.
   - Jika user tanya nilai tunggal, JANGAN tampilkan tabel, cukup print jawabannya
   - Jika user tanya ranking/list, tampilkan SATU tabel ringkas saja
   - JANGAN tampilkan multiple displays (stat + tabel + tabel lagi)

3. **JANGAN print debug/diagnostik ke user**:
   - JANGAN: print(df.head()), print(df.describe()), print(df['col'].unique())
   - JANGAN: print("Tipe data:", df.dtypes)
   - JANGAN: print("Contoh data:", ...)

## Contoh Jawaban BENAR
```python
# User: "Bagaimana tren RFT di 2025?"
# BENAR - Penjelasan singkat + tabel jika perlu
rft_trend = df[df['YEAR']==2025].groupby('MONTH')['%RFT'].mean() * 100
print(f"Rata-rata RFT di 2025 adalah {{rft_trend.mean():.1f}}%.")
print(f"Tren: {{'Meningkat' if trend > 0 else 'Menurun' if trend < 0 else 'Stabil'}} dari Oktober ke November.")
display(rft_trend.reset_index(), label="RFT per Bulan")
```

## Aturan Bahasa Output
1. JANGAN tampilkan list/dict Python mentah - jelaskan dalam kalimat
2. Format angka: 91% bukan 0.91, ribuan dengan titik
3. Gunakan kalimat lengkap, bahasa Indonesia natural
4. **JANGAN TAWARKAN LANJUTAN** - Setelah jawaban lengkap, STOP. Jangan print "Ada pertanyaan lanjutan?" atau "Mau saya bantu?"
5. **IKUTI BAHASA USER** - Jika user bertanya dalam bahasa Inggris, jawab dalam bahasa Inggris. Jika user minta bahasa tertentu (misal "answer in English"), patuhi permintaan tersebut.

## Aturan Coding - WAJIB IKUTI!
1. LANGSUNG gunakan variable `df` - JANGAN buat variabel baru untuk DataFrame.
2. **HANYA GUNAKAN KOLOM DI ATAS** - Jangan buat kolom baru seperti MONTH_NUM. Gunakan kolom yang sudah ada.
3. **MODUL TERSEDIA**: Hanya `pd`, `np`, `re`. JANGAN import sklearn, scipy, atau modul lain.
4. **HANDLE NaN**: Selalu gunakan `errors='coerce'` dan `dropna()` sebelum operasi numerik:
   - `pd.to_numeric(df['col'], errors='coerce').dropna()`
   - Jangan langsung `.astype(int)` tanpa handle NaN dulu
5. Untuk pencarian teks: `df[df['KOLOM'].str.contains('query', case=False, na=False)]`
6. Handle empty: `if result.empty or len(result) == 0: print("Data tidak tersedia")`

Balas HANYA dengan blok kode Python (```python ... ```).
"""

# Sampling config - keep small to avoid AI copying data
SAMPLE_SIZE = 5  # only show 5 rows for structure reference

# Prompt for explaining methodology and results
_EXPLAIN_SYSTEM = """\
Kamu adalah asisten analisis data yang membantu menjelaskan hasil query.

## Tugas:
Berikan penjelasan singkat yang menjawab pertanyaan user dengan cara PERCAKAPAN yang natural.

## Format Jawaban (2 bagian):

### Bagian 1: Insight (Wajib)
Jawab pertanyaan user secara LANGSUNG dengan bahasa natural:
- Sebut nama/identifier spesifik dari data
- Sertakan angka penting (gunakan format yang mudah dibaca: 91% bukan 0.91)
- Beri konteks atau perbandingan jika relevan
- 2-4 bullet points maksimal

### Bagian 2: Metodologi (Wajib)
Jelaskan SINGKAT bagaimana data didapat, contoh:
"Saya menggunakan data [nama tabel], kemudian mengelompokkan berdasarkan [kolom] dan menghitung [metrik]. Hasilnya disortir untuk menemukan [jawaban]."

## Contoh Output yang BENAR:

**Insight:**
• Line 14 memiliki rata-rata RFT tertinggi (91%), diikuti Line 23 (89%) dan Line 20 (89%)
• Dari 7 line yang dianalisis, perbedaan performa berkisar 74% hingga 91%

**Metodologi:**
Saya menganalisis data produksi, mengelompokkan berdasarkan kolom LINE, lalu menghitung rata-rata PCT_RFT untuk masing-masing line. Hasilnya disortir dari tertinggi ke terendah.

---

Ada pertanyaan lanjutan tentang data ini? Silakan tanya!
"""



# Prompt to verify if the answer is satisfactory or needs retry
_VERIFY_SYSTEM = """\
Kamu adalah Auditor QA yang kritis. Tugasmu adalah mengevaluasi apakah output kode Python berhasil menjawab pertanyaan user atau gagal (misal: data tidak ditemukan).

## Input
1. Pertanyaan User
2. Output Eksekusi Python

## Aturan Evaluasi
Analisis apakah output tersebut:
1. **BERHASIL**: Menjawab pertanyaan (termasuk jika jawabannya adalah "0" atau angka valid lainnya).
2. **GAGAL / DATA TIDAK ADA**: Output mengatakan "Data tidak tersedia", "Kosong", "Tidak ditemukan", atau error.

## Output Format
Jawab HANYA dengan salah satu format berikut:

1. Jika BERHASIL:
   PASS

2. Jika GAGAL (perlu retry):
   RETRY: [Saran spesifik untuk percobaan berikutnya]

   Contoh Saran:
   - "Coba gunakan fuzzy match untuk nama kolom"
   - "Coba kurangi filter kondisi (misal hapus filter bulan/tahun)"
   - "Cek apakah nama 'X' ditulis berbeda di data"
"""


def _build_system_prompt(df: DataFrame, table_description: str = None, column_descriptions: dict = None) -> str:
    cols = ", ".join(f"{c} ({df[c].dtype})" for c in df.columns)
    n_rows = len(df)
    
    # Only show first 5 rows for structure reference
    sample_df = df.head(SAMPLE_SIZE)
    sample = sample_df.to_csv(index=False)
    
    # Build description section
    desc_parts = []
    if table_description:
        desc_parts.append(f"## Deskripsi Tabel:\n{table_description}")
    
    if column_descriptions:
        desc_parts.append("## Deskripsi Kolom:")
        for col, desc in column_descriptions.items():
            if col in df.columns:
                desc_parts.append(f"- **{col}**: {desc}")
    
    description_section = "\n\n".join(desc_parts)
    
    return _SYSTEM_PROMPT.format(
        columns=cols, 
        sample=sample, 
        total_rows=n_rows,
        description_section=description_section
    )


def _extract_code(text: str) -> str:
    """Extract the first ```python ... ``` block from the response."""
    import re
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Fallback: assume entire response is code
    return text.strip()


def _fuzzy_match(series: pd.Series, query: str, threshold: int = 85) -> pd.Series:
    """Return a boolean Series where True means the value fuzzy-matches the query.
    
    More strict matching - query words must be found in value, not just similar.
    
    Matching priority:
    1. Exact substring: "DONG JIN" in "DONG JIN TEXTILE CO" -> match
    2. All query words present: "JIN DONG" matches "DONG JIN TEXTILE" -> match  
    3. Fuzzy match: "DONGJIN" matches "DONG JIN" -> match
    """
    import re
    
    # Normalize query
    query = str(query).upper().strip()
    query_words = set(re.findall(r'\w+', query))
    
    if not query_words:
        return pd.Series([False] * len(series), index=series.index)
    
    def check_match(val):
        if pd.isna(val):
            return False
        val_str = str(val).upper()
        
        # 1. Exact substring check (fastest)
        if query in val_str:
            return True
            
        # 2. All words check (order independent)
        val_words = set(re.findall(r'\w+', val_str))
        if query_words.issubset(val_words):
            return True
            
        # 3. Fuzzy check (slower, only if needed)
        # Simple fuzzy: check if query without spaces is in value without spaces
        query_nospace = query.replace(" ", "")
        val_nospace = val_str.replace(" ", "")
        if query_nospace in val_nospace:
            return True
            
        return False

    return series.apply(check_match)


def _safe_exec(code: str, df: DataFrame) -> tuple[str, List[dict]]:
    """
    Execute generated code safely and capture output.
    Returns: (output_string, list_of_streamlit_components)
    """
    import io
    import pandas as pd
    import numpy as np
    import re as re_module
    import datetime
    from fuzzywuzzy import fuzz as fuzzywuzzy_fuzz
    
    buf = io.StringIO()
    ui_components = []
    
    # Native UI Output Function
    def display(data, label=None, **kwargs):
        """
        Display data in the Native UI.
        
        Args:
            data: The data to display (DataFrame, int, str, list, dict)
            data: The data to display (DataFrame, int, str, list, dict)
            label: Optional label for metrics or sections
            type: Optional type override (e.g., 'clarification')
        """
        # Handling explicit type override
        if kwargs.get('type') == 'clarification' and isinstance(data, dict):
            ui_components.append({
                "type": "clarification",
                "question": data.get("question", "Mohon perjelas maksud Anda"),
                "options": data.get("options", []),
                "label": label
            })
            return

        # 1. DataFrame -> Table
        if isinstance(data, (pd.DataFrame, pd.Series)):
             if isinstance(data, pd.Series):
                 data = data.to_frame()
             
             display_df = _sanitize_df_for_display(data.head(50).copy())
             ui_components.append({
                 "type": "table",
                 "data": display_df.to_dict(orient='records'),
                 "columns": list(display_df.columns),
                 "total_rows": len(data),
                 "label": label
             })
             
        # 2. Number -> Stat (Metric)
        elif isinstance(data, (int, float, np.number)):
            ui_components.append({
                "type": "stat",
                "value": data,
                "label": label or "Value"
            })
            
        # 3. List/Dict -> JSON View
        elif isinstance(data, (list, dict)):
            ui_components.append({
                "type": "json",
                "data": data,
                "label": label
            })
            
        # 4. String/Other -> Text
        else:
             print(str(data)) # Fallback to standard print which is captured as text
    
    local_ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "re": re_module,
        "display": display,  # Native UI display function
    }
    try:
        with redirect_stdout(buf):
            exec(code, local_ns)  # noqa: S102
    except KeyError as exc:
        # KeyError usually means column not found
        col_name = str(exc).strip("'\"")
        available_cols = list(df.columns)
        return f"❌ Error: Kolom '{col_name}' tidak ditemukan!\n\nKolom yang tersedia: {', '.join(available_cols[:10])}" + (f" ... dan {len(available_cols)-10} lainnya" if len(available_cols) > 10 else ""), []
    except Exception as exc:
        exc_type = type(exc).__name__
        return f"❌ Execution error ({exc_type}): {str(exc)}\n\nPastikan kolom yang digunakan ada di data.", []
    output = buf.getvalue()
    
    # Return printed output directly (frontend will display it)
    # ui_components only contains display() calls (tables, stats, etc.)
        
    return output if output.strip() else "", ui_components


def _sanitize_df_for_display(df: DataFrame) -> DataFrame:
    """Convert non-serializable columns to string for display."""
    for col in df.columns:
        # Check if column has complex types (lists, dicts, objects)
        if df[col].dtype == 'object':
            try:
                # Try to see if it's safe
                df[col].head(1).to_json()
            except:
                # If not serializable, convert to string
                df[col] = df[col].astype(str)
    return df


class PandasAIClient:
    """Wrapper that asks the LLM to generate pandas code, then executes it."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        if not api_key:
            api_key = settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        
        self.client = OpenAI(api_key=api_key)
        self.model_name = model or settings.default_llm_model

    def _generate_explanation(self, user_question: str, query_result: str, ui_components: list = None) -> str:
        """Generate AI explanation of the query results."""
        # Skip explanation for errors or empty results
        if not query_result or "❌ Error" in query_result or "Execution error" in query_result:
            return ""
        
        # Skip if result is too short (probably just a simple number already explained)
        if len(query_result.strip()) < 20 and "\n" not in query_result and not ui_components:
            return ""

        # Build full result including tables from ui_components
        full_result = query_result
        if ui_components:
            for comp in ui_components:
                if comp.get("type") == "table" and comp.get("data"):
                    # Include table data in explanation context
                    import pandas as pd
                    table_df = pd.DataFrame(comp["data"])
                    full_result += f"\n\n### Tabel: {comp.get('label', 'Data')}\n{table_df.head(10).to_string()}"

        try:
            # Pass format instructions as system, actual data as input
            response = self.client.responses.create(
                model=self.model_name,
                instructions=_EXPLAIN_SYSTEM,
                input=f"## Pertanyaan User:\n{user_question}\n\n## Hasil Query (Data Aktual):\n{full_result}",
            )
            return response.output_text
        except Exception as e:
            return f"Gagal generate penjelasan: {str(e)}"

    def _verify_response_result(self, prompt: str, output: str) -> str:
        """
        Uses LLM to verify if the result implies data not found/failure and suggests a retry.
        Returns: "PASS" or "RETRY: <advice>"
        """
        # Quick check for obvious failures to save token
        if not output.strip() or "Error" in output:
            return "RETRY: Output kosong atau error eksekusi."

        try:
            response = self.client.responses.create(
                model=self.model_name,
                instructions=_VERIFY_SYSTEM,
                input=f"## Pertanyaan User:\n{prompt}\n\n## Output Eksekusi:\n{output}",
            )
            return response.output_text.strip()
        except Exception as e:
            logger.warning(f"Verification failed: {e}")
            return "PASS"  # Default to pass if verification fails to avoid infinite loops



    def ask(self, df: DataFrame, prompt: str, explain: bool = True, 
            table_description: str = None, column_descriptions: dict = None,
            history: List[dict] = None) -> QAResult:
        """
        Ask a question about the DataFrame with iterative retry (max 3 attempts).
        
        Args:
            df: The DataFrame to query
            prompt: User's question
            explain: If True, generate AI explanation of results (default: True)
            table_description: Optional description of the table
            column_descriptions: Optional descriptions of specific columns
            history: Optional list of previous messages [{"role": "user"|"assistant", "content": "..."}]
            
        Returns:
            QAResult with response, code, and optional explanation
        """
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        MAX_ITERATIONS = 3
        error_history = []
        validation_notes = []
        system_prompt = _build_system_prompt(df, table_description, column_descriptions)
        last_failed_code = ""
        
        logger.info(f"Starting ask() with prompt: {prompt[:50]}...")
        
        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.info(f"=== Iteration {iteration}/{MAX_ITERATIONS} ===")
            try:
                # Build messages with error context if retry
                current_prompt = prompt
                
                # Add History Context (only on first iteration, or always? Always is safer for context)
                history_context = ""
                if history:
                    history_context = "## Riwayat Percakapan (Context):\n"
                    # Limit to last 5 exchanges to save tokens
                    recent_history = history[-10:] 
                    for msg in recent_history:
                        role = "User" if msg.get("role") == "user" else "Assistant"
                        content = msg.get("content", "")
                        # Truncate long content
                        if len(content) > 500:
                            content = content[:500] + "...(truncated)"
                        history_context += f"- {role}: {content}\n"
                    history_context += "\n## Pertanyaan Baru:\n"
                
                if error_history:
                    # Add error context for retry - instruct to try different approach WITHOUT debug prints
                    error_context = "\n\n⚠️ RETRY - PERCOBAAN SEBELUMNYA GAGAL:\n"
                    for idx, err in enumerate(error_history[-2:], 1):
                        error_context += f"Attempt {err['iteration']} Error: {err['error']}\n"
                        if 'approach' in err and err['approach']:
                             error_context += f"Saran Perbaikan: {err['approach']}\n"
                             
                    error_context += "\n⚡ INSTRUKSI PERBAIKAN (JANGAN print debug, langsung jawab):\n"
                    error_context += "1. Ikuti saran perbaikan di atas.\n"
                    error_context += "2. Jika filter terlalu ketat, coba longgarkan.\n"
                    error_context += "3. Gunakan fuzzy match jika mencari teks.\n"
                    error_context += f"USER QUESTION: {prompt}"
                    current_prompt = history_context + error_context
                else:
                    # Normal prompt with history
                    current_prompt = history_context + prompt if history_context else prompt
                
                # Generate code
                response = self.client.responses.create(
                    model=self.model_name,
                    instructions=system_prompt,
                    input=current_prompt,
                )
                generated_text = response.output_text
                code = _extract_code(generated_text)
                
                # Execute Code
                output, ui_components = _safe_exec(code, df)
                
                # 1. Check for execution error
                if "❌ Error" in output or "❌ Execution error" in output:
                    print(f"[DEBUG QA] Iteration {iteration}: Execution error detected")
                    raise Exception(output)
                
                # 2. Verify Result Quality with LLM
                # Only verify if we haven't exhausted retries (no point verifying last attempt if we return it anyway)
                # But actually we might want to flag it as error for the final return.
                verification = self._verify_response_result(prompt, output)
                
                if verification.startswith("RETRY:"):
                    advice = verification.replace("RETRY:", "").strip()
                    logger.info(f"Iteration {iteration} result unsatisfiable: {advice}")
                    
                    # If this is the last iteration, we accept the result but maybe add a note?
                    # Or we just let it fall through to the return. 
                    # The user wants "reiterate until max tries". 
                    
                    if iteration < MAX_ITERATIONS:
                        raise Exception(f"Output unsatisfiable: {advice}")
                    else:
                        # Last iteration failed check - stick with it but maybe explain why?
                        # Or fall through to standard success return which will generate explanation
                        pass

                # If success (or last iteration forced success)
                explanation = ""
                if explain:
                    # Filter out internal table representations from explanation input to save tokens/confusion
                    explanation = self._generate_explanation(prompt, output, ui_components)
                
                return QAResult(
                    prompt=prompt,
                    response=output,
                    code=code,
                    explanation=explanation,
                    ui_components=ui_components,
                    iterations_used=iteration
                )

            except Exception as e:
                logger.warning(f"Iteration {iteration} failed/rejected: {e}")
                
                # Extract clean error message for context
                err_msg = str(e)
                if "Output unsatisfiable:" in err_msg:
                    err_msg = err_msg.replace("Output unsatisfiable:", "").strip()
                
                error_history.append({
                    "iteration": iteration,
                    "error": str(e), # Keep full error for logging
                    "code": code if 'code' in locals() else "",
                    "approach": err_msg # Use the advice as the approach for next time
                })
                last_failed_code = code if 'code' in locals() else ""
        
        # If all retries failed - provide user-friendly response (technical details in methodology)
        fallback_response = """Maaf, saya tidak dapat menemukan data yang Anda minta setelah beberapa percobaan.

Beberapa kemungkinan:
• Data spesifik yang dicari memang tidak ada dalam tabel
• Filter (tahun/bulan/nama) mungkin tidak cocok dengan data

Saran saya:
• Coba tanyakan "Tampilkan sample data" untuk melihat isi tabel
• Coba kurangi filter (misal: tanya data setahun penuh dulu)
"""
        
        return QAResult(
            prompt=prompt,
            response=fallback_response,
            has_error=True,
            failed_code=last_failed_code,
            validation_notes=[e['error'] for e in error_history]
        )
