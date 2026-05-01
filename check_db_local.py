import sqlite3

def check_schema():
    try:
        conn = sqlite3.connect('gestion_examens_s1.db')
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        # List columns for main tables
        for table in ['professeur', 'salles', 'salle', 'examens', 'surveillance']:
            try:
                cursor.execute(f"PRAGMA table_info({table[0] if isinstance(table, tuple) else table})")
                cols = cursor.fetchall()
                if cols:
                    print(f"\nTable {table}: {[c[1] for c in cols]}")
            except Exception as e:
                 print(f"\nCould not read {table}: {e}")
        
        # Check a few rows of professeur to see "Non spécifié"
        cursor.execute("SELECT nom_prof, charge_surv FROM professeur LIMIT 10")
        profs = cursor.fetchall()
        print(f"\nSample Profs: {profs}")

    except Exception as e:
        print(f"Error: {e}")
            
if __name__ == '__main__':
    check_schema()
