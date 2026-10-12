
from app.database import Base, engine
from app import models


def main():
    expected_tables = {
        "interview_sessions",
        "questions",
        "candidate_answers",
        "evaluations",
        "documents",
        "document_chunks",
    }

    print("Creating missing database tables...")
    Base.metadata.create_all(bind=engine)
    print("Table creation completed.")

    with engine.connect() as connection:
        result = connection.exec_driver_sql(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
        )
        existing_tables = {row[0] for row in result.fetchall()}

    missing_tables = expected_tables - existing_tables

    for table_name in sorted(expected_tables & existing_tables):
        print(f"Verified table: {table_name}")

    if missing_tables:
        raise RuntimeError(
            f"Missing tables: {sorted(missing_tables)}"
        )

    print("All six tables verified successfully.")


if __name__ == "__main__":
    main()
