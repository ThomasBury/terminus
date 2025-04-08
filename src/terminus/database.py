from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from terminus.config import settings  # Import the settings instance from config.py

# Create the SQLAlchemy engine using the database URL from settings.
# The connect_args is set for SQLite; adjust if you change the DB backend.
engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False
    },  # Necessary for SQLite concurrency in development.
)

# Configure session factory
SessionLocal = sessionmaker(bind=engine)

# Create a declarative base for the ORM models.
Base = declarative_base()


def get_session():
    """
    Dependency to provide a SQLAlchemy session to FastAPI endpoints.

    This function is used as a dependency in FastAPI endpoints to provide a
    SQLAlchemy session. It ensures that the session is properly closed after
    the request is processed.

    Yields
    ------
    session : Session
        A SQLAlchemy session object.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_all_tables():
    """
    For development only – ensures all tables are created.

    This function creates all tables defined in the models if they do not
    already exist. It is intended for use during development to set up the
    database schema.

    Notes
    -----
    This function should not be used in a production environment as it may
    overwrite existing data.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_all_tables()
    print("All tables created.")
    print("DB Path:", settings.database_url / "terminus.db")
