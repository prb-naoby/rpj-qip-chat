"""
Full document ingestion script.
Ingests all 40 documents from DOCUMENT_ROOT_PATH.
"""
from app.document_ingestion import ingest_all_documents

def main():
    print("Starting full document ingestion...")
    print("=" * 60)
    
    result = ingest_all_documents(dry_run=False, skip_existing=False)
    
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Total files: {result.get('total_files', 0)}")
    print(f"Processed: {result.get('processed', 0)}")
    print(f"Success: {result.get('success', 0)}")
    print(f"Failed: {result.get('failed', 0)}")
    print(f"Skipped: {result.get('skipped', 0)}")
    
    if result.get('collection_stats'):
        stats = result['collection_stats']
        print(f"\nCollection stats:")
        print(f"  Points: {stats.get('points_count', 'N/A')}")
        print(f"  Status: {stats.get('status', 'N/A')}")
    
    # Show any failures
    failures = [d for d in result.get('details', []) if d and not d.get('success')]
    if failures:
        print(f"\n{len(failures)} failures:")
        for f in failures[:10]:
            print(f"  - {f.get('filename', 'unknown')}: {f.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
