import sqlite3
import random
from config import DATABASE_PATH

def migrate():
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    # Get all service IDs
    cursor.execute("SELECT id FROM services")
    services = cursor.fetchall()
    
    durations = [30, 60, 90, 120]
    updated_count = 0
    
    for (s_id,) in services:
        rand_duration = random.choice(durations)
        cursor.execute("UPDATE services SET duration = ? WHERE id = ?", (rand_duration, s_id))
        updated_count += 1
        
    conn.commit()
    conn.close()
    print(f"Migration complete. Updated {updated_count} services with random durations.")

if __name__ == "__main__":
    migrate()
