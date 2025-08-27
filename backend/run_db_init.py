#!/usr/bin/env python3
"""
Database initialization script for YudaiV3
"""
import argparse
import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def main():
    """Run database initialization"""
    parser = argparse.ArgumentParser(description="YudaiV3 Database Initialization")
    parser.add_argument("--reset", action="store_true", help="Reset sample data if it exists")
    args = parser.parse_args()
    
    try:
        print("🚀 Starting YudaiV3 Database Initialization...")
        print("=" * 60)
        
        # Import and run the database initialization
        from db.init_db import create_database
        
        success = create_database()
        
        if success:
            print("\n🎉 SUCCESS: Database initialization completed!")
            print("✅ All tables created with correct schema")
            print("✅ Sample data populated (or already exists)")
            print("✅ Database is ready for use")
            
            # Handle reset if requested
            if args.reset:
                print("\n🔄 Resetting sample data...")
                from db.database import reset_sample_data
                try:
                    reset_sample_data()
                    print("✅ Sample data reset successfully")
                except Exception as e:
                    print(f"⚠️  Sample data reset failed: {e}")
            
            return True
        else:
            print("\n❌ FAILED: Database initialization failed!")
            return False
            
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
