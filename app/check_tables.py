
from app.database import Base, engine
from app import models

print("REGISTERED MODELS:")
print(sorted(Base.metadata.tables.keys()))

print("\nCreating any missing tables...")
Base.metadata.create_all(bind=engine)

print("\nTABLES IN SUPABASE:")

with engine.connect() as connection:
    result = connection.exec_driver_sql(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
              'interview_sessions',
              'questions',
              'candidate_answers',
              'evaluations',
              'documents',
              'document_chunks'
          )
        ORDER BY table_name
        """
    )

    for row in result.fetchall():
        print(row[0])
