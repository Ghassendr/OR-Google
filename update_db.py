import mysql.connector
import os

def run_sql_file(filename):
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'gestion_examens_s1'),
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        with open(filename, 'r', encoding='utf-8') as f:
            sql = f.read()
            
        # Split semicolon but ignore within strings
        # Simple split is usually enough for these types of files
        for statement in sql.split(';'):
            if statement.strip():
                cursor.execute(statement)
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Sucessfully executed {filename}")
    except Exception as e:
        print(f"Error executing {filename}: {str(e)}")

if __name__ == "__main__":
    run_sql_file('timetable_schema.sql')
