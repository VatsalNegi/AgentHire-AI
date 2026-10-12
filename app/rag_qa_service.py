
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm_service import chat_completion
from app.retrieval_service import search_documents


def answer_from_documents(
    db: Session,
    question: str,
    limit: int = 5,
    document_type: str | None = None,
    owner_id: UUID | None = None,
) -> dict:
    """Answer a question using retrieved document context."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    # 1. Retrieve relevant chunks from Supabase.
    results = search_documents(
        db=db,
        query=question.strip(),
        limit=limit,
        document_type=document_type,
        owner_id=owner_id,
    )

    if not results:
        return {
            "question": question,
            "answer": (
                "I couldn't find relevant information in the indexed "
                "documents. Please upload or index a suitable document."
            ),
            "sources": [],
        }

    # 2. Build context and source references.
    context_parts = []
    sources = []

    for result in results:
        source_number = len(sources) + 1

        context_parts.append(
            f"[Source {source_number}]\n"
            f"Filename: {result['filename']}\n"
            f"Chunk: {result['chunk_index']}\n"
            f"Content:\n{result['content']}"
        )

        sources.append(
            {
                "source_number": source_number,
                "document_id": str(result["document_id"]),
                "filename": result["filename"],
                "chunk_index": result["chunk_index"],
            }
        )

    context = "\n\n".join(context_parts)

    # 3. Ask the LLM to answer using the retrieved context.
    prompt = f"""
You are AgentHire AI, a professional hiring assistant.

Answer the user's question using only the document context below.

Rules:
1. Give the user a direct, well-organized answer.
2. Use headings and bullet points when useful.
3. Never reveal internal reasoning, analysis, or drafting notes.
4. Do not describe your process of selecting or comparing sources.
5. Do not invent skills, responsibilities, or qualifications.
6. If the documents do not contain enough information, say so clearly.
7. Cite factual claims using citations such as [Source 1].
8. Only cite source numbers that appear in the supplied context.
9. Do not end with an incomplete sentence or citation.

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{question.strip()}

Provide a clear, concise answer with source citations.
""".strip()

    answer = chat_completion(prompt)

    # 4. Return the answer and source metadata.
    return {
        "question": question.strip(),
        "answer": answer,
        "sources": sources,
    }
