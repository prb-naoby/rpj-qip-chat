"""
Re-ingest the failed PNG image.
"""
from app.document_ingestion import ingest_single_document
from app.onedrive_documents import list_document_files

def main():
    print("Finding the failed PNG file...")
    files = list_document_files()
    
    # Find the PNG
    png_files = [f for f in files if f["name"].lower().endswith(".png")]
    
    if not png_files:
        print("No PNG files found")
        return
    
    for png in png_files:
        print(f"\nRe-ingesting: {png['name']}")
        result = ingest_single_document(png)
        print(f"Result: {result}")

if __name__ == "__main__":
    main()
