#!/usr/bin/env python3
"""
Quick functionality test script for Letterboxd Reviewer backend
"""

import sys
import os

# Add backend to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

def test_imports():
    """Test if all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        from database.connection import init_db, get_db
        print("✅ Database connection imports OK")
    except ImportError as e:
        print(f"❌ Database connection import failed: {e}")
        return False
    
    try:
        from database.models import Profile, Rating, Review
        print("✅ Database models imports OK")
    except ImportError as e:
        print(f"❌ Database models import failed: {e}")
        return False
    
    try:
        from database.repository import ProfileRepository, RatingRepository
        print("✅ Repository imports OK")
    except ImportError as e:
        print(f"❌ Repository import failed: {e}")
        return False
    
    try:
        from core.analyzer import UnifiedLetterboxdAnalyzer
        print("✅ Analyzer imports OK")
    except ImportError as e:
        print(f"❌ Analyzer import failed: {e}")
        return False
    
    try:
        from config import settings
        print("✅ Config imports OK")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
        
    return True

def test_database():
    """Test database initialization"""
    print("\n🗄️ Testing database...")
    
    try:
        from database.connection import init_db, engine
        init_db()
        print("✅ Database initialized successfully")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✅ Database connection test OK")
            
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_data_directories():
    """Test data directory structure"""
    print("\n📁 Testing data directories...")
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    required_dirs = [
        os.path.join(base_dir, 'data'),
        os.path.join(base_dir, 'data', 'scraped'),
        os.path.join(base_dir, 'data', 'exports'),
        os.path.join(base_dir, 'data', 'backups')
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path} exists")
        else:
            print(f"❌ {dir_path} missing")
            all_exist = False
            # Create missing directories
            os.makedirs(dir_path, exist_ok=True)
            print(f"🔧 Created {dir_path}")
    
    return all_exist

def main():
    print("🎬 Letterboxd Reviewer - Functionality Test")
    print("=" * 50)
    
    tests = [
        test_data_directories,
        test_imports,
        test_database,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 All functionality tests passed!")
        print("✅ Backend appears to be fully functional")
        return 0
    else:
        print("⚠️ Some functionality tests failed")
        print("🔧 Check the errors above and fix them")
        return 1

if __name__ == "__main__":
    sys.exit(main())
