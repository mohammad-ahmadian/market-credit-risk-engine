from sqlalchemy import create_engine
from config.config import DATABASE_URL

def get_db_engine():
    """Creates and returns a SQLAlchemy Database Engine."""
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        print("Successfully connected to PostgreSQL database.")
        return engine
    except Exception as e:
        print(f"Error connecting to Database: {e}")
        raise e