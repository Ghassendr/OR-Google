import mysql.connector
import os
import re

def sync_proffers():
    cfg = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'gestion_examens'),
        'charset': 'utf8mb4'
    }
    
    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor()
        
        print("--- Modifying Table Schema ---")
        # Add columns if they don't exist
        try:
            cursor.execute("ALTER TABLE proffer ADD COLUMN grade VARCHAR(100) DEFAULT NULL")
            print("Added 'grade' column.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Column already exists
                print("'grade' column already exists.")
            else: raise
            
        try:
            cursor.execute("ALTER TABLE proffer ADD COLUMN charge_surv INT DEFAULT 0")
            print("Added 'charge_surv' column.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Column already exists
                print("'charge_surv' column already exists.")
            else: raise

        print("\n--- Parsing proffer.sql ---")
        with open('proffer.sql', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find all INSERT statements
        # Format: (1, 'BEN SALAH Mohamed', 'Maître Assistant', 5),
        pattern = r"\((\d+),\s*'([^']*)',\s*(?:'([^']*)'|NULL),\s*(\d+)\)"
        matches = re.findall(pattern, content)
        
        print(f"Found {len(matches)} professor records to update.")
        
        update_query = "UPDATE proffer SET grade = %s, charge_surv = %s WHERE id_proffer = %s"
        update_count = 0
        
        for match in matches:
            id_prof, name, grade, charge = match
            # If grade was NULL it's an empty string or None
            final_grade = grade if grade else None
            
            cursor.execute(update_query, (final_grade, int(charge), int(id_prof)))
            update_count += 1
            
        conn.commit()
        print(f"Successfully updated {update_count} professors.")
        
        cursor.close()
        conn.close()
        print("\n--- Synchronization Complete ---")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    sync_proffers()
