"""
Test search query on ingested documents.
"""
from app.qdrant_service import search_chunks

def main():
    query = "frekuensi audit quality"
    print(f"Searching for: '{query}'")
    print("=" * 60)
    
    results = search_chunks(query, limit=5)
    
    if not results:
        print("No results found")
        return
    
    print(f"Found {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        print(f"--- Result {i} (score: {result['score']:.4f}) ---")
        print(f"File: {result['filename']}")
        print(f"Chunk: {result['chunk_index']}")
        print(f"Text preview: {result['text'][:300]}...")
        print()

if __name__ == "__main__":
    main()
