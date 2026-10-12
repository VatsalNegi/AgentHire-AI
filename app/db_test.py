
from sqlalchemy import create_engine, text
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


def main():
    settings = Settings()

    if not settings.database_url:
        raise RuntimeError(
        "DATABASE_URL is missing. Check your .env file."
    )

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 15},
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT current_database(), version()")
            )

            row = result.fetchone()

            if row is None:
                raise RuntimeError("Database query returned no rows.")

            database_name, version = row

            print(f"Connected to database: {database_name}")
            print(f"PostgreSQL version: {version.split(',')[0]}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
