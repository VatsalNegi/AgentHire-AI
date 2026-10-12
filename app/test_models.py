
from app.database import Base
from app import models


def _assert_expected_tables_registered():
    expected_tables = {
        "interview_sessions",
        "questions",
        "candidate_answers",
        "evaluations",
    }
    actual_tables = set(Base.metadata.tables.keys())
    missing = expected_tables - actual_tables
    assert not missing, f"Missing tables: {missing}"


def test_interview_tables_are_registered():
    _assert_expected_tables_registered()


def main():
    print("Models imported successfully.")

    actual_tables = set(Base.metadata.tables.keys())

    for table_name in sorted(actual_tables):
        print(f"Registered table: {table_name}")

    _assert_expected_tables_registered()

    print("Model registration test passed.")


if __name__ == "__main__":
    main()
