
from app.database import Base, SessionLocal, engine


def main():
    print("Database engine initialized successfully.")
    print(f"Database dialect: {engine.dialect.name}")
    print(f"Registered tables: {list(Base.metadata.tables.keys())}")

    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
        print("Supabase connection verified.")

    print("Session factory initialized:", SessionLocal is not None)


if __name__ == "__main__":
    main()
