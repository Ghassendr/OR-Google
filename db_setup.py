import mysql.connector
import json
import os

def get_db_connection():
    cfg = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': 'gestion_examens_s1',
        'charset': 'utf8mb4'
    }
    return mysql.connector.connect(**cfg)

def export_to_json():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Export Filières to filier.json
        print("Exporting filières...")
        cursor.execute("SELECT id_filaire AS id, nom_filaire AS Filiere, abreviation_filaire AS abrevation, annee AS Niveau FROM filaire")
        filiere_rows = cursor.fetchall()
        
        # We need "Effectif" which isn't in the SQL but is in filier.json
        # Let's try to preserve Effectif if JSON exists
        old_filieres = {}
        if os.path.exists('filier.json'):
            try:
                with open('filier.json', 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        for item in content:
                            old_filieres[item.get('Filiere', '')] = item.get('Effectif', 0)
            except: pass

        for row in filiere_rows:
            row['Effectif'] = old_filieres.get(row['Filiere'], 0)

        with open('filier.json', 'w', encoding='utf-8') as f:
            json.dump(filiere_rows, f, indent=4, ensure_ascii=False)

        # Export Matieres to matieres.json
        print("Exporting matières...")
        cursor.execute("""
            SELECT m.id_mataire AS id, m.nom_mataire AS nom, m.id_proffe AS id_professeur, 
                   p.nom_professeur AS professeur, 
                   f.nom_filaire AS filiere, f.annee
            FROM mataire m
            LEFT JOIN proffer p ON m.id_proffe = p.id_proffer
            LEFT JOIN filaire f ON m.filaire_id = f.id_filaire
        """)
        matiere_rows = cursor.fetchall()
        with open('matieres.json', 'w', encoding='utf-8') as f:
            json.dump(matiere_rows, f, indent=4, ensure_ascii=False)

        print("Export complete!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error during export: {e}")

if __name__ == "__main__":
    export_to_json()
