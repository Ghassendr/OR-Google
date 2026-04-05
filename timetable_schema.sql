-- Schema for Emploi du Temps (Timetable)
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
  FOREIGN KEY (`matiere_id`) REFERENCES `mataire`(`id_mataire`),
  FOREIGN KEY (`prof_id`) REFERENCES `proffer`(`id_proffer`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sample data for Licence SI 2EME (filiere_id=22)
-- S01-1101 Algèbre 1 (matiere_id=1)
-- S40-1301 Probabilité et statistique (matiere_id=657)
-- S44-1305 Programmation Java (matiere_id=661)

INSERT INTO `emploi_du_temps` (`filiere_id`, `matiere_id`, `prof_id`, `jour`, `heure_debut`, `heure_fin`, `salle`, `type_session`) VALUES
(22, 1, 1, 'Lundi', '08:30:00', '10:00:00', 'Amphi K', 'CM'),
(22, 657, 2, 'Lundi', '10:15:00', '11:45:00', 'Salle M1', 'TD'),
(22, 661, 3, 'Mardi', '08:30:00', '11:45:00', 'Labo I1', 'TP'),
(22, 1, 1, 'Mercredi', '13:30:00', '15:00:00', 'Amphi K', 'CM'),
(22, 657, 2, 'Jeudi', '08:30:00', '10:00:00', 'Salle M2', 'CM');
