
import mysql.connector
from werkzeug.security import generate_password_hash
import os

def setup_db():
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

        # Create user table
        print("Creating 'user' table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS `user` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `username` varchar(50) NOT NULL UNIQUE,
            `password_hash` varchar(255) NOT NULL,
            `role` enum('ADMIN', 'PROFESSOR') NOT NULL,
            `prof_id` int(11) DEFAULT NULL,
            PRIMARY KEY (`id`),
            FOREIGN KEY (`prof_id`) REFERENCES `professeur`(`id_professeur`) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ''')

        # Seed admin user
        username = 'admin'
        password = 'admin123'
        password_hash = generate_password_hash(password)

        print(f"Checking if admin user '{username}' exists...")
        cursor.execute("SELECT id FROM `user` WHERE username = %s", (username,))
        if cursor.fetchone():
            print(f"Admin user '{username}' already exists. Updating password...")
            cursor.execute("UPDATE `user` SET password_hash = %s WHERE username = %s", (password_hash, username))
        else:
            print(f"Creating admin user '{username}'...")
            cursor.execute("INSERT INTO `user` (username, password_hash, role) VALUES (%s, %s, 'ADMIN')", (username, password_hash))

        conn.commit()
        cursor.close()
        conn.close()
        print("Database setup completed successfully.")
    except Exception as e:
        print(f"Error setting up database: {e}")

if __name__ == '__main__':
    setup_db()
