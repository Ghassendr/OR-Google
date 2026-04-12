import mysql.connector
import json
import os

def migrate():
    config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',
        'database': 'gestion_examens_s1',
        'charset': 'utf8mb4'
    }

    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()

        # 1. Run migrations
        with open('db_migration.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
        
        print("Tables created successfully.")

        # 2. Migrate Rooms (class.json)
        if os.path.exists('class.json'):
            with open('class.json', 'r', encoding='utf-8') as f:
                rooms = json.load(f)
                insert_room = "INSERT IGNORE INTO salle (name, capacity, building, sous_cap1, sous_cap2) VALUES (%s, %s, %s, %s, %s)"
                for r in rooms:
                    cursor.execute(insert_room, (
                        r['Salle'], 
                        r['CapaciteTotal'], 
                        r['Salle'][0], 
                        r.get('SousCapacite1'), 
                        r.get('SousCapacite2')
                    ))
            print(f"{len(rooms)} rooms migrated.")

        # 3. Create initial history entry from placement.json if exists
        if os.path.exists('placement.json'):
            with open('placement.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                cursor.execute(
                    "INSERT INTO distribution_history (name, data_json, params_json, is_active) VALUES (%s, %s, %s, %s)",
                    ("Distribution Actuelle", json.dumps(data), "{}", 1)
                )
            print("Current placement migrated to history.")

        conn.commit()
        cursor.close()
        conn.close()
        print("Migration and data import complete.")

    except Exception as e:
        print(f"Erreur: {str(e)}")

if __name__ == "__main__":
    migrate()
