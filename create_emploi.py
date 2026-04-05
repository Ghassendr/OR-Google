import mysql.connector

cfg = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'gestion_examens_s1',
    'charset': 'utf8mb4'
}

query = """
CREATE TABLE IF NOT EXISTS `emploi_du_temps` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `filiere_id` INT NOT NULL,
  `matiere_id` INT NOT NULL,
  `prof_id` INT DEFAULT NULL,
  `jour` ENUM('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi') NOT NULL,
  `heure_debut` TIME NOT NULL,
  `heure_fin` TIME NOT NULL,
  `salle` VARCHAR(50) NOT NULL,
  `type_session` ENUM('CM', 'TD', 'TP') NOT NULL DEFAULT 'CM',
  FOREIGN KEY (`filiere_id`) REFERENCES `filaire`(`id_filaire`),
  FOREIGN KEY (`matiere_id`) REFERENCES `matiere`(`id_matiere`),
  FOREIGN KEY (`prof_id`) REFERENCES `professeur`(`id_professeur`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

try:
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()
    print("Table created successfully")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
