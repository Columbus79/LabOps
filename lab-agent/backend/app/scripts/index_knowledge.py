import argparse
from pathlib import Path

from app.database import SessionLocal
from app.services.kb_service import KB_DIR, SUPPORTED_DOCUMENTS, _document_chunks, index_markdown_documents


def main():
    parser = argparse.ArgumentParser(description="Incrementally index explicitly selected LabOps office documents")
    parser.add_argument("--apply", action="store_true", help="Write chunks and embeddings to PostgreSQL")
    parser.add_argument("--directory", type=Path, help="Explicit source directory required with --apply")
    args = parser.parse_args()
    if args.apply and args.directory is None:
        parser.error("--apply requires --directory; private knowledge is never indexed implicitly")
    directory = args.directory or KB_DIR
    if not args.apply:
        files = sorted(path for path in directory.iterdir()
                       if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENTS)
        for path in files:
            document_id, _, chunks = _document_chunks(path)
            print(f"{document_id}: {len(chunks)} chunks")
        print(f"Dry run: {len(files)} documents; no database or API calls made. Pass --apply --directory to index.")
        return
    db = SessionLocal()
    try:
        print(index_markdown_documents(db, directory))
    finally:
        db.close()


if __name__ == "__main__":
    main()
