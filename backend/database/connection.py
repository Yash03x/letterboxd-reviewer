from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os
from typing import Generator

# Database configuration
# Use absolute path for database to avoid path issues
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "..", "data", "letterboxd_analyzer.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},  # Only needed for SQLite
        echo=False  # Set to True for SQL debugging
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database dependency for FastAPI
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables (run this once to initialize)
def create_tables():
    from .models import Base
    Base.metadata.create_all(bind=engine)

def check_and_add_column(table_name: str, column_name: str, column_def: str) -> bool:
    """Check if column exists and add it if not"""
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]
            
            if column_name not in columns:
                print(f"Adding {column_name} column to {table_name} table...")
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
                conn.commit()
                print(f"✓ Added {column_name} column successfully!")
                return True
            else:
                print(f"✓ {column_name} column already exists in {table_name}")
                return True
    except Exception as e:
        print(f"Error with {column_name} column: {e}")
        return False

# Initialize database
def init_db():
    """Initialize database with tables"""
    create_tables()
    
    # Run migrations for new columns
    print("🔄 Running database migrations...")
    success = check_and_add_column("ratings", "is_liked", "is_liked BOOLEAN DEFAULT 0")
    
    if success:
        print("✅ Database initialized and migrated successfully!")
    else:
        print("⚠️  Database initialized but migrations may have issues")

if __name__ == "__main__":
    init_db()