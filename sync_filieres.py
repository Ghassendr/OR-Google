import json
import mysql.connector
import os

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'gestion_examens_s1'
}

def sync_filiere_data():
    if not os.path.exists('filier.json'):
        print("filier.json not found. Skipping sync.")
        return

    try:
        with open('filier.json', 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        for item in items:
            nom = item.get('Filiere')
            annee_raw = item.get('Niveau')
            effectif = item.get('Effectif', 0)
            
            # Map annee to DB enum: '1ERE', '2EME', '3EME'
            db_annee = '1ERE'
            if '2eme' in annee_raw: db_annee = '2EME'
            elif '3eme' in annee_raw: db_annee = '3EME'
            elif 'master' in annee_raw: db_annee = '3EME' # Mapping masters to 3rd year block for placement
            
            print(f"Syncing {nom} ({db_annee}) -> Effectif: {effectif}")
            
            # Clean nom (remove L_ prefix if exists in JSON but not in DB)
            nom_clean = nom.replace('L_', '')
            
            # Trial 1: Exact match by abbreviation
            cursor.execute("UPDATE filaire SET effectif = %s WHERE abreviation_filaire = %s AND annee = %s", (effectif, nom_clean, db_annee))
            
            if cursor.rowcount == 0:
                # Trial 2: Match by name containing the JSON filiere string
                cursor.execute("UPDATE filaire SET effectif = %s WHERE instr(nom_filaire, %s) > 0 AND annee = %s", (effectif, nom_clean, db_annee))

        conn.commit()
        print("Synchronization completed successfully.")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error during synchronization: {e}")

if __name__ == "__main__":
    sync_filiere_data()
