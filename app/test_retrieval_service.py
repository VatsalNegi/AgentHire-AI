
from app.database import SessionLocal
from app.retrieval_service import search_documents


def main():
    db = SessionLocal()

    try:
        results = search_documents(
            db=db,
            query="What should a Python developer know about APIs and databases?",
            limit=3,
            document_type="job_description",
        )

        print(f"Results found: {len(results)}")

        for index, result in enumerate(results, start=1):
            print(f"\nResult {index}")
            print(f"Filename: {result['filename']}")
            print(f"Chunk: {result['chunk_index']}")
            print(f"Cosine distance: {result['cosine_distance']:.4f}")
            print(f"Content: {result['content'][:250]}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
