# 🎓 ISSAT Sousse — Système de Gestion des Examens

Plateforme web complète pour la planification, la distribution et la surveillance des examens de l'ISSAT Sousse.

---

## 🚀 Lancement du Serveur

```bash
python server_new.py
```

Le serveur démarre sur **http://127.0.0.1:5000**

> ⚠️ Assurez-vous que MySQL est démarré via XAMPP Control Panel avant de lancer le serveur.

---

## 🔐 Comptes par Défaut

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Administrateur | `admin` | `admin123` |
| Enseignant | — | Lien magique (Magic Link) par email |

---

## 🗂️ Pages Principales

| URL | Description |
|---|---|
| `/` | Dashboard de surveillance (rapport.html) |
| `/login-page` | Connexion Admin / Enseignant |
| `/register-page` | Inscription d'un nouveau compte |
| `/prof` | Répertoire académique des professeurs |
| `/absence-page` | Portail de déclaration d'absences (Enseignants) |
| `/import-page` | Import de données (Admin uniquement) |

---

## 🗄️ Base de Données

**Nom :** `gestion_examens_s1`  
**Hôte :** `127.0.0.1:3306`  
**Utilisateur :** `root` (sans mot de passe)

### Tables

---

### `professeur`
Contient tous les enseignants de l'établissement.

| Colonne | Type | Description |
|---|---|---|
| `id_professeur` | INT PK AUTO | Identifiant unique |
| `nom_prenom` | VARCHAR(120) | Nom complet |
| `grade` | VARCHAR(100) | Grade académique (MAB, MC, PA…) |
| `charge_surv` | TINYINT | Charge de surveillance totale assignée |
| `rest_charger` | INT | Charge de surveillance restante |
| `email` | VARCHAR(255) | Email académique (ex: nom.prenom@issatso.com) |

---

### `matiere`
Liste des matières enseignées avec leur lien filière/professeur.

| Colonne | Type | Description |
|---|---|---|
| `id_matiere` | INT PK AUTO | Identifiant unique |
| `code_matiere` | VARCHAR(20) | Code officiel de la matière |
| `nom_matiere` | VARCHAR(200) | Intitulé complet |
| `id_filaire` | INT FK | Filière associée → `filaire.id_filaire` |
| `id_professeur` | INT FK | Professeur responsable → `professeur.id_professeur` |
| `has_examen` | TINYINT(1) | 1 = a un examen planifié |
| `has_ds` | TINYINT(1) | 1 = a un Devoir Surveillé |
| `jour_num` | TINYINT | Jour d'examen (1=Lundi … 6=Samedi) |

---

### `filaire` (Filières)
Toutes les filières de formation de l'établissement.

| Colonne | Type | Description |
|---|---|---|
| `id_filaire` | INT PK AUTO | Identifiant unique |
| `nom_filaire` | VARCHAR(150) | Nom complet de la filière |
| `abreviation_filaire` | VARCHAR(50) | Abréviation (ex: GL, RT, GE…) |
| `code_filaire` | VARCHAR(20) | Code filière |
| `type_filaire` | ENUM | `LICENCE`, `MASTER_PRO`, `MASTER_RECHERCHE`, `INGENIEUR`, `PREPA` |
| `annee` | ENUM | `1ERE`, `2EME`, `3EME` |
| `effectif` | INT | Nombre d'étudiants inscrits |

---

### `salle`
Salles d'examen disponibles.

| Colonne | Type | Description |
|---|---|---|
| `id` | INT PK AUTO | Identifiant |
| `name` | VARCHAR(50) UNIQUE | Nom/numéro de la salle |
| `capacity` | INT | Capacité totale |
| `sous_cap1` | INT | Sous-capacité groupe 1 |
| `sous_cap2` | INT | Sous-capacité groupe 2 |

---

### `salle_filieres`
Affectation des filières aux salles par session (matin / après-midi).

| Colonne | Type | Description |
|---|---|---|
| `salle_name` | VARCHAR(50) FK | Salle concernée |
| `type_session` | VARCHAR(10) | `matin` ou `apmidi` |
| `id_filiere1` | INT FK | Première filière assignée |
| `id_filiere2` | INT FK | Deuxième filière assignée (optionnel) |

---

### `emploi_du_temps`
Emploi du temps officiel généré avec créneaux, salles et professeurs.

| Colonne | Type | Description |
|---|---|---|
| `id` | INT PK AUTO | Identifiant |
| `filiere_id` | INT FK | Filière |
| `matiere_id` | INT FK | Matière |
| `prof_id` | INT FK | Professeur |
| `jour` | VARCHAR | Jour de la semaine |
| `heure_debut` | TIME | Heure de début |
| `heure_fin` | TIME | Heure de fin |
| `salle` | VARCHAR | Salle assignée |
| `type_session` | VARCHAR | Type de séance |

---

### `user`
Comptes utilisateurs pour la connexion à la plateforme.

| Colonne | Type | Description |
|---|---|---|
| `id` | INT PK AUTO | Identifiant |
| `username` | VARCHAR(50) UNIQUE | Nom d'utilisateur |
| `password_hash` | VARCHAR(255) | Mot de passe hashé (pbkdf2:sha256) |
| `role` | ENUM | `ADMIN` ou `PROFESSOR` |
| `prof_id` | INT FK | Lien vers `professeur.id_professeur` |

---

### `declarations`
Créneaux d'indisponibilité déclarés par les enseignants.

| Colonne | Type | Description |
|---|---|---|
| `id` | INT PK AUTO | Identifiant |
| `prof_id` | INT FK | Professeur concerné |
| `jour` | VARCHAR(20) | Jour (ex: `Lundi`) |
| `seance` | VARCHAR(10) | Séance (ex: `S1`, `S2`, `S3`, `S4`) |

---

### `magic_tokens`
Tokens pour l'authentification sans mot de passe des enseignants (Magic Link).

| Colonne | Type | Description |
|---|---|---|
| `id` | INT PK AUTO | Identifiant |
| `prof_id` | INT FK | Professeur concerné |
| `token` | VARCHAR(36) | UUID unique du token |
| `expires_at` | DATETIME | Date d'expiration (15 min) |
| `used` | TINYINT(1) | 0 = non utilisé, 1 = consommé |

---

## 🔌 API Principales

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/me` | Utilisateur connecté (session) |
| POST | `/login` | Connexion admin |
| POST | `/logout` | Déconnexion |
| POST | `/api/register` | Créer un compte |
| GET | `/api/professors` | Liste des professeurs |
| GET | `/api/matieres` | Liste des matières |
| GET | `/api/filieres` | Liste des filières |
| POST | `/api/auth/request-link` | Envoyer un Magic Link |
| GET | `/verify-token?token=...` | Valider un Magic Link |
| GET | `/api/auth/me-prof` | Profil enseignant connecté |
| POST | `/api/declarations` | Sauvegarder les indisponibilités |
| POST | `/api/prof/matieres` | Mettre à jour le DS des matières |
| POST | `/api/generate-surveillance` | Lancer l'algorithme OR-Tools |
| GET | `/api/surveillance-stats` | Statistiques de surveillance |

---

## 🛠️ Stack Technique

| Composant | Technologie |
|---|---|
| Backend | Python / Flask |
| Base de données | MySQL (via XAMPP) |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Algorithme | OR-Tools (CP-SAT Solver) |
| Auth Enseignant | JWT + Magic Link |
| Auth Admin | Session Flask |

---

## 📁 Fichiers Importants

| Fichier | Rôle |
|---|---|
| `server_new.py` | Serveur Flask principal |
| `report.html` | Dashboard de surveillance |
| `login.html` | Page de connexion (Admin + Enseignant) |
| `absence.html` | Portail de déclaration d'absences |
| `prof.html` | Répertoire des professeurs |
| `generate_surv_ortools.py` | Algorithme de génération de surveillance |
| `sidebar-component.js` | Composant sidebar réutilisable |
| `gestion_examens_s1.sql` | Dump de la base de données |

---

*© 2026 ISSAT Sousse — Système de Gestion Académique*
