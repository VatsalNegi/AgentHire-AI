
from app.database import SessionLocal
from app.rag_qa_service import answer_from_documents


def main() -> None:
    question = (
        "What skills and responsibilities are required "
        "for the Junior Python Developer role?"
    )

    db = SessionLocal()

    try:
        print("Testing RAG question answering...")
        result = answer_from_documents(
            db=db,
            question=question,
            limit=3,
            document_type="job_description",
        )

        print("\nQuestion:")
        print(result["question"])

        print("\nAnswer:")
        print(result["answer"])

        print("\nSources:")
        for source in result["sources"]:
            print(
                f"- {source['filename']} "
                f"(chunk {source['chunk_index']}, "
                f"source {source['source_number']})"
            )

        print("\nRAG question-answering test completed.")

    except Exception as exc:
        print(f"\nRAG test failed: {type(exc).__name__}: {exc}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
