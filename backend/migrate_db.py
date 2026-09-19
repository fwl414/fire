import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fire_ai_agent.db")

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(devices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("install_date", "DATE"),
            ("last_maintenance", "DATE"),
            ("next_maintenance", "DATE"),
            ("description", "TEXT DEFAULT ''"),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"Adding column {col_name} to devices table...")
                cursor.execute(f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
