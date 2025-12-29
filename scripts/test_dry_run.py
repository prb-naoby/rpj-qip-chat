"""
Dry run test script for document ingestion.
"""
from app.document_ingestion import discover_documents, ingest_single_document
from app.qdrant_service import ensure_collection_exists

def main():
    # Discover files
    print("Discovering documents...")
    files = discover_documents()
    print(f"Found {len(files)} supported documents")

    if not files:
        print("No documents found - check DOCUMENT_ROOT_PATH in .env")
        return

    print("\nFirst 5 documents:")
    for f in files[:5]:
        size_kb = f.get("size", 0) / 1024
        print(f"  - {f['name']} ({size_kb:.1f} KB)")
    
    # Test with first document
    first = files[0]
    print(f"\n--- Testing first document: {first['name']} ---")
    
    # Ensure collection exists first
    print("Ensuring Qdrant collection exists...")
    ensure_collection_exists()
    
    # Ingest single document
    print("Ingesting document...")
    result = ingest_single_document(first)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
