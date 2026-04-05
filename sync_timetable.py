import mysql.connector
import os
from datetime import time

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database='gestion_examens_s1'
    )

def sync():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        print("Fetching matieres with day assignments...")
        # Updated to match gestion_examens_s1 structure
        cursor.execute("SELECT id_matiere, id_filaire, id_professeur, jour_num, has_ds, has_examen FROM matiere WHERE jour_num IS NOT NULL")
        matieres = cursor.fetchall()

        day_map = {1: 'Lundi', 2: 'Mardi', 3: 'Mercredi', 4: 'Jeudi', 5: 'Vendredi', 6: 'Samedi'}
        time_slots = [
            ('08:30:00', '10:00:00'),
            ('10:15:00', '11:45:00'),
            ('12:00:00', '13:30:00'),
            ('13:45:00', '15:15:00'),
            ('15:30:00', '17:00:00')
        ]

        # Reset the table
        print("Clearing existing emploi_du_temps entries...")
        cursor.execute("DELETE FROM emploi_du_temps")

        print(f"Syncing {len(matieres)} subjects...")
        
        day_filiere_counts = {}

        for m in matieres:
            day_name = day_map.get(m['jour_num'])
            if not day_name: continue
            
            f_id = m['id_filaire']
            key = f"{f_id}_{day_name}"
            count = day_filiere_counts.get(key, 0)
            
            if count < len(time_slots):
                start, end = time_slots[count]
                
                t_session = 'CM'
                if m['has_examen'] == 1: t_session = 'EXAM'
                elif m['has_ds'] == 1: t_session = 'TD'
                
                cursor.execute("""
                    INSERT INTO emploi_du_temps (filiere_id, matiere_id, prof_id, jour, heure_debut, heure_fin, salle, type_session)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (f_id, m['id_matiere'], m['id_professeur'], day_name, start, end, 'A DEFINIR', t_session))
                
                day_filiere_counts[key] = count + 1

        conn.commit()
        print(f"Database sync complete! {len(matieres)} entries processed.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    sync()
