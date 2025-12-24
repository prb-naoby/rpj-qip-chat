"""
Excel Multi-Table Patterns Module (OOP)

Defines parsers for different Excel file formats with multiple tables per sheet.

Usage:
    from app.excel_patterns import ExcelPatternProcessor
    
    processor = ExcelPatternProcessor()
    tables = processor.process(Path("Loss C-grade Agustus 2025.xlsx"), pattern="Loss C-Grade")
    
    # Returns Dict[str, DataFrame] with table names as keys

Available Patterns:
    - "Loss C-Grade": Monthly loss reports with Defect/Production/Return/Total Loss tables
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type

import pandas as pd
from pandas import DataFrame


# =============================================================================
# BASE CLASSES
# =============================================================================

class BasePattern(ABC):
    """Base class for Excel file patterns."""
    
    name: str = "base"
    description: str = "Base pattern"
    
    # Rows to exclude from data (summary rows)
    EXCLUDE_LINE_VALUES = ['TOTAL', 'AQL', 'Painting', 'Total', 'total']
    EXCLUDE_AREA_VALUES = ['Total', 'TOTAL', 'total']
    
    # Month name mappings for date parsing
    MONTH_NAMES = {
        'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
        'january': 1, 'february': 2, 'march': 3, 'may': 5,
        'june': 6, 'july': 7, 'august': 8, 'october': 10, 'december': 12
    }
    
    def __init__(self):
        self.file_path: Optional[Path] = None
        self.month: Optional[int] = None
        self.year: Optional[int] = None
    
    @abstractmethod
    def process(self, file_path: Path, unpivot: bool = True) -> Dict[str, DataFrame]:
        """Process the Excel file and return extracted tables."""
        pass
    
    def extract_month_year_from_filename(self, filename: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract month and year from filename."""
        name = filename.lower()
        
        year_match = re.search(r'(20\d{2})', name)
        year = int(year_match.group(1)) if year_match else None
        
        month = None
        for month_name, month_num in self.MONTH_NAMES.items():
            if month_name in name:
                month = month_num
                break
        
        return month, year
    
    def normalize_date(self, raw_date: str, sheet_name: str, month: int, year: int) -> str:
        """Normalize date to ISO format YYYY-MM-DD."""
        raw_str = str(raw_date).strip()
        
        day_match = re.match(r'^(\d{1,2})', raw_str)
        if day_match:
            day = int(day_match.group(1))
        else:
            try:
                day = int(sheet_name)
            except ValueError:
                day = 1
        
        for month_name, month_num in self.MONTH_NAMES.items():
            if month_name in raw_str.lower():
                month = month_num
                year_match = re.search(r'(20\d{2})', raw_str)
                if year_match:
                    year = int(year_match.group(1))
                break
        
        try:
            return f"{year:04d}-{month:02d}-{day:02d}"
        except:
            return raw_str
    
    def is_numeric_sheet(self, name: str) -> bool:
        """Check if sheet name is a number (date identifier)."""
        try:
            int(name)
            return True
        except ValueError:
            return False


# =============================================================================
# PATTERN: Loss C-Grade
# =============================================================================

class LossCGradePattern(BasePattern):
    """
    Parser for Loss C-Grade monthly reports.
    
    Table structure per sheet:
    - Row 4-29: Defect Loss (with horizontal blocks for shifts)
    - Row 31-40: Production Loss
    - Row 42-46: Return Loss
    - Row 48-50: Total Loss
    """
    
    name = "Loss C-Grade"
    description = "Monthly outsole loss/defect reports"
    
    # Table definitions
    TABLES = [
        {
            "name": "Defect Loss",
            "header_row": 3,
            "data_start": 4,
            "data_end": 29,
            "has_horizontal_blocks": True,
        },
        {
            "name": "Production Loss",
            "header_row": 30,
            "header_row_2": 31,
            "data_start": 32,
            "data_end": 40,
        },
        {
            "name": "Return Loss",
            "header_row": 41,
            "header_row_2": 42,
            "data_start": 43,
            "data_end": 46,
        },
        {
            "name": "Total Loss",
            "header_row": 47,
            "header_row_2": 48,
            "data_start": 49,
            "data_end": 50,
        },
    ]
    
    # Defect types for unpivot filtering
    DEFECT_TYPES = [
        'Dirty', 'Contamination', 'Color Bleeding', 'Bubble', 'Yellowing',
        'Slide Mold', 'Undercure', 'Overcure', 'Shading Color', 'Less Material',
        'Double Skin', 'Damage Mold', 'Peel Off', 'Over Trimming', 'Metal', 'AQL'
    ]
    
    def process(self, file_path: Path, unpivot: bool = True) -> Dict[str, DataFrame]:
        """Process a Loss C-Grade Excel file."""
        self.file_path = file_path
        print(f"\n[PROCESS] {file_path.name} (Pattern: {self.name})")
        
        # Extract month/year from filename
        self.month, self.year = self.extract_month_year_from_filename(file_path.name)
        if not self.month or not self.year:
            print(f"  [WARN] Could not extract month/year, using current date")
            self.month = datetime.now().month
            self.year = datetime.now().year
        
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            print(f"  [ERROR] Could not open file: {e}")
            return {}
        
        # Get numeric sheets (date identifiers)
        date_sheets = [s for s in xls.sheet_names if self.is_numeric_sheet(s)]
        print(f"  Found {len(date_sheets)} date sheets")
        print(f"  Extracted: Month={self.month}, Year={self.year}")
        
        # Storage for each table type
        tables: Dict[str, List[DataFrame]] = {t["name"]: [] for t in self.TABLES}
        
        # Process each date sheet
        for sheet_name in date_sheets:
            try:
                df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            except Exception as e:
                print(f"    [WARN] Could not read sheet {sheet_name}: {e}")
                continue
            
            # Extract and normalize date
            try:
                date_cell = df_raw.iloc[2, 1]
                raw_date = str(date_cell).strip() if pd.notna(date_cell) else sheet_name
            except:
                raw_date = sheet_name
            
            date_value = self.normalize_date(raw_date, sheet_name, self.month, self.year)
            
            # Extract each table
            for table_def in self.TABLES:
                if table_def.get("has_horizontal_blocks"):
                    table_df = self._extract_horizontal_table(df_raw, table_def, date_value)
                else:
                    table_df = self._extract_simple_table(df_raw, table_def, date_value)
                
                if table_df is not None and len(table_df) > 0:
                    tables[table_def["name"]].append(table_df)
        
        # Merge and optionally unpivot
        result = {}
        for table_name, dfs in tables.items():
            if dfs:
                combined = pd.concat(dfs, ignore_index=True)
                
                if unpivot:
                    combined = self._unpivot_table(combined, table_name)
                
                result[table_name] = combined
                print(f"  {table_name}: {len(combined)} rows")
            else:
                print(f"  {table_name}: No data found")
        
        return result
    
    def _extract_horizontal_table(
        self, df_raw: DataFrame, table_def: dict, date_value: str
    ) -> Optional[DataFrame]:
        """Extract table with horizontal block stacking (Defect Loss)."""
        try:
            header_row = table_def["header_row"]
            data_start = table_def["data_start"]
            data_end = min(table_def["data_end"], len(df_raw) - 1)
            
            if data_start >= len(df_raw):
                return None
            
            header = df_raw.iloc[header_row].fillna('').astype(str).tolist()
            line_positions = [i for i, h in enumerate(header) if h.strip() == 'Line']
            
            if not line_positions:
                return None
            
            all_blocks = []
            for block_idx, start_col in enumerate(line_positions):
                end_col = line_positions[block_idx + 1] if block_idx + 1 < len(line_positions) else len(header)
                
                block_header = header[start_col:end_col]
                clean_header = [h.strip() if h.strip() and h.lower() != 'nan' else f"Col_{i}" 
                               for i, h in enumerate(block_header)]
                
                block_data = df_raw.iloc[data_start:data_end + 1, start_col:end_col].copy()
                block_data.columns = clean_header[:len(block_data.columns)]
                
                block_data.insert(0, 'Date', date_value)
                block_data.insert(1, 'Shift', block_idx + 1)
                
                all_blocks.append(block_data)
            
            if not all_blocks:
                return None
            
            combined = pd.concat(all_blocks, ignore_index=True)
            combined = combined.dropna(how='all')
            
            if 'Line' in combined.columns:
                combined = combined[combined['Line'].notna() & (combined['Line'].astype(str).str.strip() != '')]
                combined = combined[~combined['Line'].astype(str).str.strip().isin(self.EXCLUDE_LINE_VALUES)]
            
            # Filter out blank rows (no Model or no Output/Target)
            if 'Model' in combined.columns and 'Output' in combined.columns:
                # Placeholder values that indicate "no production"
                placeholder_models = ['//', 'OFF', 'OOF', 'OFF/OFF/OFF', 'OOF/OOF/OOF', '-', '--', '']
                
                # Row is valid if it has: real Model name AND Output value > 0
                has_real_model = (
                    combined['Model'].notna() & 
                    (combined['Model'].astype(str).str.strip() != '') &
                    (~combined['Model'].astype(str).str.strip().str.upper().isin([m.upper() for m in placeholder_models]))
                )
                has_output = pd.to_numeric(combined['Output'], errors='coerce').fillna(0) > 0
                combined = combined[has_real_model & has_output]
            
            return combined.reset_index(drop=True)
            
        except Exception as e:
            print(f"    [WARN] Error extracting horizontal table: {e}")
            return None
    
    def _extract_simple_table(
        self, df_raw: DataFrame, table_def: dict, date_value: str
    ) -> Optional[DataFrame]:
        """Extract simple table without horizontal blocks."""
        try:
            header_row = table_def["header_row"]
            data_start = table_def["data_start"]
            data_end = min(table_def["data_end"], len(df_raw) - 1)
            
            if data_start >= len(df_raw):
                return None
            
            header = df_raw.iloc[header_row].fillna('').astype(str).tolist()
            
            # Combine with second header row if exists
            if "header_row_2" in table_def:
                header2 = df_raw.iloc[table_def["header_row_2"]].fillna('').astype(str).tolist()
                header = [h2.strip() if h2.strip() and h2.lower() != 'nan' else h1.strip() 
                         for h1, h2 in zip(header, header2)]
            
            # Clean header names
            cleaned_header = []
            seen = {}
            for i, h in enumerate(header):
                h = str(h).strip()
                if not h or h.lower() == 'nan':
                    h = f"Col_{i}"
                if h in seen:
                    seen[h] += 1
                    h = f"{h}_{seen[h]}"
                else:
                    seen[h] = 0
                cleaned_header.append(h)
            
            # Find end of first block
            first_block_end = len(cleaned_header)
            for i, h in enumerate(cleaned_header):
                if i > 10 and h.strip() in ['Area', 'Line']:
                    first_block_end = i
                    break
            
            cleaned_header = cleaned_header[:first_block_end]
            
            data_rows = df_raw.iloc[data_start:data_end + 1, :first_block_end].copy()
            data_rows.columns = cleaned_header[:len(data_rows.columns)]
            data_rows.insert(0, 'Date', date_value)
            data_rows = data_rows.dropna(how='all')
            
            # Filter rows with data
            data_cols = data_rows.columns[1:]
            mask = data_rows[data_cols].apply(
                lambda row: any(pd.notna(v) and str(v).strip() != '' for v in row),
                axis=1
            )
            data_rows = data_rows[mask]
            
            if len(data_rows) == 0:
                return None
            
            # Filter summary rows
            if 'Area' in data_rows.columns:
                data_rows = data_rows[~data_rows['Area'].astype(str).str.strip().isin(self.EXCLUDE_AREA_VALUES)]
            
            return data_rows.reset_index(drop=True)
            
        except Exception as e:
            print(f"    [WARN] Error extracting simple table: {e}")
            return None
    
    def _unpivot_table(self, df: DataFrame, table_name: str) -> DataFrame:
        """Unpivot table from wide to long format."""
        if table_name == "Defect Loss":
            id_cols = ['Date', 'Shift', 'Line', 'Model', 'Mold', 'Target', 'Output', '%Output',
                      'Total', '%Deffect Loss', 'Repair', '%Repair', 'Nama TL']
        else:
            id_cols = ['Date', 'Area', 'Mold', 'Target', 'Output', '%Output',
                      'Total', '%Production Loss', '%Return Loss', '%Total Loss', 'Repair', '%Repair']
        
        existing_ids = [c for c in id_cols if c in df.columns]
        value_columns = [c for c in df.columns if c not in existing_ids]
        
        # Filter to defect columns only
        value_columns = [c for c in value_columns 
                        if any(dt.lower() in c.lower() for dt in self.DEFECT_TYPES)]
        
        if not value_columns:
            return df
        
        melted = pd.melt(df, id_vars=existing_ids, value_vars=value_columns,
                        var_name='Defect_Type', value_name='Value')
        
        melted['Value'] = pd.to_numeric(melted['Value'], errors='coerce')
        melted = melted[melted['Value'].notna() & (melted['Value'] != 0)]
        
        return melted.reset_index(drop=True)


# =============================================================================
# PATTERN: Physical Test Lab
# =============================================================================

class PhysicalTestLabPattern(BasePattern):
    """
    Parser for Physical Test Lab reports.
    
    Structure:
    - Single sheet (usually 'actual' or sheet 0)
    - Two-row header: Row 0 has test type names, Row 1 has result/std/remarks
    - Data starts at row 2
    
    Month is extracted from filename (e.g., "AGUSTUS", "SEPTEMBER").
    """
    
    name = "Physical Test Lab"
    description = "Physical test lab reports with abrasion, hardness, etc."
    
    # Base columns that identify each sample
    BASE_COLUMNS = ['NO LAB', 'CUST', 'ART', 'TOOL', 'MODEL', 'COLOUR', 'MASFOR', 
                    'TOTAL ORDER', 'TEST QTY', 'PRESS DATE', 'LAB IN', 'LAB OUT']
    
    def process(self, file_path: Path, unpivot: bool = True) -> Dict[str, DataFrame]:
        """Process a Physical Test Lab Excel file."""
        self.file_path = file_path
        print(f"\n[PROCESS] {file_path.name} (Pattern: {self.name})")
        
        # Extract month/year from filename
        self.month, self.year = self.extract_month_year_from_filename(file_path.name)
        if self.year:
            print(f"  Extracted: Month={self.month}, Year={self.year}")
        
        try:
            df_raw = pd.read_excel(file_path, sheet_name=0, header=None)
        except Exception as e:
            print(f"  [ERROR] Could not open file: {e}")
            return {}
        
        print(f"  Raw shape: {df_raw.shape}")
        
        # Build combined header from two rows
        df = self._process_two_row_header(df_raw)
        
        if df is None or len(df) == 0:
            return {"Physical Test Lab": pd.DataFrame()}
        
        # Add source file info
        df.insert(0, 'Source_File', file_path.name)
        
        # Add month if extracted
        if self.month and self.year:
            df.insert(1, 'Report_Month', f"{self.year:04d}-{self.month:02d}")
        
        # Filter out empty rows
        df = df.dropna(how='all')
        if 'NO LAB' in df.columns:
            df = df[df['NO LAB'].notna() & (df['NO LAB'].astype(str).str.strip() != '')]
        
        # Clean up column names
        df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
        
        print(f"  Physical Test Lab: {len(df)} rows")
        
        return {"Physical Test Lab": df.reset_index(drop=True)}
    
    def _process_two_row_header(self, df_raw: DataFrame) -> Optional[DataFrame]:
        """Process the two-row header structure."""
        try:
            # Row 0: test type names (or column names for base columns)
            # Row 1: result/std/remarks labels
            row0 = df_raw.iloc[0].fillna('').astype(str).tolist()
            row1 = df_raw.iloc[1].fillna('').astype(str).tolist()
            
            # Build combined column names
            combined_header = []
            current_test_type = ""
            
            for i, (r0, r1) in enumerate(zip(row0, row1)):
                r0 = r0.strip()
                r1 = r1.strip()
                
                # If row0 has a value, it's either a base column or a test type
                if r0 and r0.lower() != 'nan':
                    current_test_type = r0
                    
                    # Check if it's a base column (no sub-columns)
                    if r1 in ['', 'nan'] or r1.lower() == 'nan':
                        # Base column - use row0 value directly
                        combined_header.append(r0)
                    else:
                        # Test type with sub-column
                        combined_header.append(f"{r0}_{r1}")
                elif r1 and r1.lower() != 'nan':
                    # Sub-column under current test type
                    if current_test_type:
                        combined_header.append(f"{current_test_type}_{r1}")
                    else:
                        combined_header.append(r1)
                else:
                    combined_header.append(f"Col_{i}")
            
            # Extract data (from row 2 onwards)
            data = df_raw.iloc[2:].copy()
            data.columns = combined_header[:len(data.columns)]
            
            return data
            
        except Exception as e:
            print(f"    [WARN] Error processing header: {e}")
            import traceback
            traceback.print_exc()
            return None


# =============================================================================
# PATTERN REGISTRY & PROCESSOR
# =============================================================================

# Registry of available patterns
PATTERN_REGISTRY: Dict[str, Type[BasePattern]] = {
    "Loss C-Grade": LossCGradePattern,
    "Physical Test Lab": PhysicalTestLabPattern,
}


class ExcelPatternProcessor:
    """
    Main processor for Excel files with multiple tables.
    
    Data is accumulated across multiple process() calls. Use reset() to clear.
    
    Usage:
        processor = ExcelPatternProcessor()
        
        # Process multiple files - data accumulates
        processor.process(Path("file1.xlsx"), pattern="Loss C-Grade")
        processor.process(Path("file2.xlsx"), pattern="Loss C-Grade")
        
        # Get accumulated tables
        tables = processor.get_tables()
        
        # Or process fresh (clears existing data)
        tables = processor.process(Path("file.xlsx"), pattern="Loss C-Grade", append=False)
        
        # Reset accumulated data
        processor.reset()
    """
    
    def __init__(self):
        self.patterns = PATTERN_REGISTRY
        self._tables: Dict[str, DataFrame] = {}
        self._processed_files: List[str] = []
    
    def list_patterns(self) -> List[str]:
        """List available pattern names."""
        return list(self.patterns.keys())
    
    def get_pattern(self, name: str) -> BasePattern:
        """Get a pattern instance by name."""
        if name not in self.patterns:
            available = ", ".join(self.patterns.keys())
            raise ValueError(f"Unknown pattern '{name}'. Available: {available}")
        return self.patterns[name]()
    
    def reset(self):
        """Clear all accumulated data."""
        self._tables = {}
        self._processed_files = []
        print("[RESET] Cleared accumulated data")
    
    def get_tables(self) -> Dict[str, DataFrame]:
        """Get all accumulated tables."""
        return self._tables.copy()
    
    def get_processed_files(self) -> List[str]:
        """Get list of processed file names."""
        return self._processed_files.copy()
    
    def process(
        self,
        file_path: Path,
        pattern: str,
        unpivot: bool = True,
        append: bool = True
    ) -> Dict[str, DataFrame]:
        """
        Process an Excel file using the specified pattern.
        
        Args:
            file_path: Path to Excel file
            pattern: Pattern name (e.g., "Loss C-Grade")
            unpivot: If True, convert pivot tables to long format
            append: If True, append to existing tables. If False, clear first.
        
        Returns:
            Dict mapping table name to DataFrame (accumulated if append=True)
        """
        if not append:
            self.reset()
        
        pattern_instance = self.get_pattern(pattern)
        new_tables = pattern_instance.process(file_path, unpivot=unpivot)
        
        # Append to accumulated tables
        for table_name, df in new_tables.items():
            if table_name in self._tables and len(df) > 0:
                self._tables[table_name] = pd.concat(
                    [self._tables[table_name], df], 
                    ignore_index=True
                )
            elif len(df) > 0:
                self._tables[table_name] = df
        
        self._processed_files.append(file_path.name)
        
        return self.get_tables()
    
    def process_batch(
        self,
        file_paths: List[Path],
        pattern: str,
        unpivot: bool = True,
        append: bool = True
    ) -> Dict[str, DataFrame]:
        """
        Process multiple Excel files at once.
        
        Args:
            file_paths: List of paths to Excel files
            pattern: Pattern name
            unpivot: If True, convert pivot tables to long format
            append: If True, append to existing tables. If False, clear first.
        
        Returns:
            Dict mapping table name to DataFrame (accumulated)
        """
        if not append:
            self.reset()
        
        for file_path in file_paths:
            self.process(file_path, pattern, unpivot=unpivot, append=True)
        
        return self.get_tables()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def process_excel(file_path: Path, pattern: str, unpivot: bool = True) -> Dict[str, DataFrame]:
    """Convenience function to process an Excel file."""
    processor = ExcelPatternProcessor()
    return processor.process(file_path, pattern, unpivot)


# =============================================================================
# MAIN (for testing)
# =============================================================================

def main():
    """Test the processor."""
    TEMP_DIR = Path(__file__).parent.parent / "temp_samples"
    target = TEMP_DIR / "Loss C-grade Agustus 2025 V2.xlsx"
    
    if not target.exists():
        print(f"[ERROR] File not found: {target}")
        return
    
    print("=" * 80)
    print("EXCEL PATTERN PROCESSOR TEST")
    print("=" * 80)
    
    processor = ExcelPatternProcessor()
    print(f"Available patterns: {processor.list_patterns()}")
    
    tables = processor.process(target, pattern="Loss C-Grade", unpivot=True)
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    for table_name, df in tables.items():
        print(f"\n--- {table_name} ---")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nFirst 5 rows:")
        print(df.head().to_string())
        
        out_path = TEMP_DIR / f"parsed_{table_name.replace(' ', '_').lower()}.csv"
        df.to_csv(out_path, index=False)
        print(f"\nSaved to: {out_path.name}")


if __name__ == "__main__":
    main()
