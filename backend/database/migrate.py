#!/usr/bin/env python3
"""
Database Migration Script
Handles adding new columns to existing database
"""

import sqlite3
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .connection import get_db, engine, DATABASE_URL
from .models import Base

def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        with engine.connect() as conn:
            # Get table info
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]  # row[1] is column name
            return column_name in columns
    except Exception as e:
        print(f"Error checking column existence: {e}")
        return False

def add_is_liked_column():
    """Add is_liked column to ratings table"""
    print("🔄 Checking if is_liked column exists in ratings table...")
    
    if check_column_exists("ratings", "is_liked"):
        print("✅ is_liked column already exists!")
        return True
    
    try:
        with engine.connect() as conn:
            print("📝 Adding is_liked column to ratings table...")
            conn.execute(text("ALTER TABLE ratings ADD COLUMN is_liked BOOLEAN DEFAULT 0"))
            conn.commit()
            print("✅ Successfully added is_liked column!")
            return True
    except Exception as e:
        print(f"❌ Error adding is_liked column: {e}")
        return False

def migrate_database():
    """Run all necessary migrations"""
    print("🚀 Starting database migration...")
    print(f"Database URL: {DATABASE_URL}")
    
    # Ensure tables exist first
    print("📋 Creating/updating tables...")
    Base.metadata.create_all(bind=engine)
    
    # Add new columns
    success = add_is_liked_column()
    
    if success:
        print("✅ Database migration completed successfully!")
    else:
        print("❌ Database migration failed!")
    
    return success

def reset_database():
    """Drop and recreate all tables (destructive!)"""
    print("⚠️  WARNING: This will delete all data!")
    confirm = input("Type 'YES' to confirm database reset: ")
    
    if confirm != 'YES':
        print("❌ Database reset cancelled.")
        return False
    
    try:
        print("🗑️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        
        print("📋 Creating tables...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ Database reset completed!")
        return True
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_database()
    else:
        migrate_database()