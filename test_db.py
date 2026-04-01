import mysql.connector
import os

def test_connection():
    cfg = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',
        'database': 'gestion_examens'
    }
    try:
        print(f"Connecting to {cfg['database']}...")
        conn = mysql.connector.connect(**cfg)
        print("Connected successfully!")
        cursor = conn.cursor()
        
        tables = ['filaire', 'proffer', 'mataire']
        for table in tables:
            try:
                cursor.execute(f"DESCRIBE {table}")
                print(f"\nTable: {table}")
                for col in cursor.fetchall():
                    print(f"  {col[0]} ({col[1]})")
            except Exception as e:
                print(f"Error describing {table}: {e}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
