
from app.database import SessionLocal
from app.rag_service import index_document


def main():
    sample_text = """
    Python developers should understand REST APIs, SQL databases,
    exception handling, unit testing, and version control.
    FastAPI is used to build APIs, while SQLAlchemy manages
    database interactions. Candidates should also understand
    authentication, authorization, and secure coding practices.
    """ * 8

    db = SessionLocal()

    try:
        result = index_document(
            db=db,
            filename="agenthire_test_job_description.txt",
            text=sample_text,
            document_type="job_description",
        )

        print("Document indexing successful.")
        print(f"Document ID: {result['document_id']}")
        print(f"Status: {result['status']}")
        print(f"Chunks created: {result['chunks_created']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
