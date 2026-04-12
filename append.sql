ALTER TABLE professeur ADD COLUMN email VARCHAR(255);
ALTER TABLE professeur ADD COLUMN rest_charger INT DEFAULT 0;

UPDATE professeur SET email = 'abdallahabdelkaderiskander@issatso.com', rest_charger = charge 
WHERE full_name = 'ABDALLAH Abdelkader Iskander';

CREATE TABLE magic_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prof_id INT NOT NULL,
    token VARCHAR(36) NOT NULL,
    expires_at DATETIME NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (prof_id) REFERENCES professeur(id) ON DELETE CASCADE
);

CREATE TABLE declarations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prof_id INT NOT NULL,
    jour VARCHAR(50) NOT NULL,
    creneau_debut TIME NOT NULL,
    creneau_fin TIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prof_id) REFERENCES professeur(id) ON DELETE CASCADE
);
