# 📚 OR-Google — Système de Gestion des Examens (ISSATso)

> **Explication complète du projet** : fichiers, technologies, architecture, et fonctionnement.

---

## 🗂️ 1. Description Générale

Ce projet est un **système automatisé de gestion des examens** pour l'**ISSATso** (Institut Supérieur des Sciences Appliquées et de Technologie de Sousse).

Il résout **trois problèmes d'optimisation** majeurs :
1. **Placement des étudiants** → Affecter chaque filière dans des salles d'examen de façon optimale (occupation ≥ 70%, max 2 filières/salle, équilibre des effectifs).
2. **Calendrier d'examens** → Organiser les examens par jour et par session (matin/après-midi).
3. **Attribution de la surveillance** → Assigner des professeurs pour surveiller chaque salle/créneau en respectant la charge de surveillance de chacun.

---

## 📁 2. Fichiers Importants et Leur Rôle

### 🔧 Fichiers Principaux

| Fichier | Rôle |
|---|---|
| `app.py` | **Serveur Flask** — Point d'entrée de l'application. Expose toutes les routes API REST et sert le dashboard HTML. |
| `report.html` | **Dashboard Frontend** — Interface utilisateur principale. Affiche les résultats de placement en temps réel. |
| `prof.html` | **Dashboard Professeurs** — Interface dédiée à la gestion et visualisation des surveillants. |
| `requirements.txt` | Liste des bibliothèques Python requises. |
| `INSTRUCTIONS.md` | Guide d'installation et de démarrage du projet. |

### ⚙️ Algorithmes d'Optimisation

| Fichier | Rôle |
|---|---|
| `exam_greedy.py` | **Solveur CP-SAT pour placement** — Utilise Google OR-Tools pour placer les étudiants dans les salles (bloc matin et bloc après-midi). Anciennement "greedy", maintenant basé sur CP-SAT. |
| `exam_placement.py` | **Solveur CP-SAT avancé** — Version plus complexe du placement avec découpage en sous-groupes (max 20 étudiants/groupe), bonus de mixité et génération du rapport HTML. |
| `exam_calendar.py` | **Calendrier des examens** — Algorithme d'organisation du planning journalier des examens. |
| `generate_surv_ortools.py` | **Solveur de surveillance CP-SAT** — Le solveur le plus complexe : attribue 2 professeurs par créneau/salle sur 6 jours, en respectant les charges et en minimisant le coût. |
| `exam_greedy_clean.py` | Version simplifiée/nettoyée du solveur de placement. |
| `version1.py` | Ancienne version du solveur (conservée pour référence). |

### 🗄️ Base de Données et Configuration

| Fichier | Rôle |
|---|---|
| `create_emploi.py` | Script SQL pour créer la table `emploi_du_temps` dans MySQL. |
| `db_setup.py` | Exporte les données MySQL vers des fichiers JSON locaux. |
| `gestion_examens_s1.sql` | Dump complet de la base de données MySQL (structure + données). |
| `timetable_schema.sql` | Schéma SQL de la table emploi du temps. |
| `solver_config.json` | Paramètres de configuration du solveur (taux min d'occupation, buffer, etc.). |

### 📊 Données JSON (Cache Local)

| Fichier | Rôle |
|---|---|
| `filier.json` | Liste des filières avec leurs effectifs. |
| `matieres.json` | Liste des matières avec professeurs et filières associées. |
| `class.json` | Liste des salles d'examen avec leurs capacités. |
| `placement.json` | Résultats du dernier placement (généré automatiquement). |
| `surveillance_cache.json` | Cache du dernier planning de surveillance généré par OR-Tools (≈800KB). |
| `calendrie_DS.json` | Calendrier des DS (devoirs surveillés). |
| `Professeurs_ISSATso.json` | Données brutes des professeurs. |

### 🔍 Scripts de Debug et Utilitaires

| Fichier | Rôle |
|---|---|
| `check_surv.py`, `check_surv2.py` | Vérification de la validité du planning de surveillance. |
| `find_contradictions.py` | Détecte les contradictions dans les données. |
| `sync_proffers.py`, `sync_timetable.py` | Synchronisation des données professeurs/emploi du temps. |
| `analyze_results.py`, `deep_analyze.py` | Analyse des résultats d'optimisation. |
| `tmp_check.py`, `tmp_check2.py`, `tmp_describe.py` | Scripts temporaires de débogage. |
| `extract_prof.py` | Extraction des données professeurs depuis la base. |

---

## 🛠️ 3. Technologies Utilisées et Pourquoi

### 🐍 Python 3
**Pourquoi ?**
- Langage de référence pour l'optimisation mathématique et la data science.
- Bibliothèque OR-Tools disponible nativement en Python via `pip`.
- Rapidité de développement pour scripts de traitement de données.

### 🌐 Flask + Flask-CORS
**Pourquoi ?**
- Framework web Python **léger** — parfait pour une API REST simple sans surcharge.
- Sert à la fois l'API JSON (routes `/api/*`) et les fichiers HTML statiques.
- `Flask-CORS` permet au dashboard JavaScript d'appeler l'API depuis le navigateur sans blocage CORS.

### 🧠 Google OR-Tools (CP-SAT Solver)
**Pourquoi ? — C'est le cœur du projet.**
- **OR-Tools** est la bibliothèque d'optimisation open-source de Google.
- Le solveur **CP-SAT** (Constraint Programming + SAT) est utilisé pour résoudre des problèmes NP-difficiles de planification.
- Il gère des **milliers de variables booléennes et entières** avec des contraintes complexes :
  - `x[fi, ri]` = nb d'étudiants de la filière `fi` dans la salle `ri`
  - Contraintes de capacité, d'équilibre, de mixité, de charge professeurs...
- Il utilise **16 workers parallèles** pour explorer l'espace de solutions rapidement.
- Alternative aux algorithmes gloutons classiques qui ne garantissent pas l'optimalité.

### 🗃️ MySQL (via `mysql-connector-python`)
**Pourquoi ?**
- Base de données relationnelle pour stocker les données permanentes : professeurs, matières, filières, salles, emplois du temps.
- Requêtes SQL complexes avec `JOIN` pour agréger les données (ex: matières + professeurs + filières en une seule requête).
- Les variables d'environnement (`DB_HOST`, `DB_USER`, etc.) permettent la configuration sans modifier le code.

### 🐼 Pandas + openpyxl
**Pourquoi ?**
- **Pandas** : lecture et manipulation de fichiers Excel/CSV uploadés par l'utilisateur.
- **openpyxl** : support des fichiers `.xlsx`.
- Permet d'importer des listes d'étudiants/filières directement depuis des tableurs Excel institutionnels.

### 🔍 Pytesseract + Pillow
**Pourquoi ?**
- **Tesseract OCR** : extraction de texte depuis des images (photos de documents, tableaux scannés).
- **Pillow** : lecture et traitement des images avant OCR.
- Permet d'importer des données depuis des documents papier numérisés (cas réel en milieu universitaire).

### 🌐 HTML + JavaScript Vanilla
**Pourquoi ?**
- Dashboard léger sans framework lourd (pas de React/Vue nécessaire ici).
- `report.html` et `prof.html` sont des SPA (Single Page Application) simples avec JavaScript natif.
- Communication avec le backend Flask via `fetch()` (API JSON).

---

## 🏗️ 4. Architecture du Projet

```
┌─────────────────────────────────────────────────────────┐
│                    COUCHE FRONTEND                       │
│  report.html  <->  prof.html  (HTML + JS Vanilla)        │
│        |                  |                             │
│   fetch() API calls    fetch() API calls                │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP (port 5000)
┌─────────────────────────▼───────────────────────────────┐
│                   COUCHE BACKEND (app.py)                │
│                                                         │
│  Routes API REST (Flask):                               │
│  ├── GET  /              -> Sert report.html            │
│  ├── GET  /prof          -> Sert prof.html              │
│  ├── GET  /get-data      -> filier.json + matieres.json │
│  ├── GET  /api/professors -> MySQL: table professeur    │
│  ├── GET  /api/matieres   -> MySQL: table matiere       │
│  ├── GET  /api/filieres   -> MySQL: table filaire       │
│  ├── GET  /api/timetable  -> MySQL: emploi_du_temps     │
│  ├── GET  /api/surveillance-stats -> Cache JSON / MySQL │
│  ├── POST /api/generate-surveillance -> Lance solveur   │
│  ├── POST /run-algorithm  -> Lance exam_greedy.py       │
│  ├── POST /upload-excel   -> Import Excel/CSV (Pandas)  │
│  └── POST /upload-ocr    -> OCR image (pytesseract)     │
│                                                         │
└──────┬──────────────────────────┬───────────────────────┘
       │                          │
┌──────▼──────────┐  ┌────────────▼───────────────────────┐
│  COUCHE DONNÉES │  │        COUCHE SOLVEURS             │
│                 │  │                                    │
│  MySQL DB:      │  │  exam_greedy.py (CP-SAT)           │
│  ├── professeur │  │  -> Placement étudiant/salle       │
│  ├── matiere    │  │                                    │
│  ├── filaire    │  │  exam_placement.py (CP-SAT avancé) │
│  ├── salle_     │  │  -> Placement avec sous-groupes    │
│  │   filieres   │  │                                    │
│  └── emploi_    │  │  generate_surv_ortools.py (CP-SAT) │
│      du_temps   │  │  -> Attribution surveillance       │
│                 │  │                                    │
│  JSON Cache:    │  │  Tous utilisent:                   │
│  ├── placement  │  │  ortools.sat.python.cp_model       │
│  ├── surv_cache │  │  -> 16 workers parallèles          │
│  └── filier.json│  │  -> Time limit: 60-120 secondes    │
└─────────────────┘  └────────────────────────────────────┘
```

---

## ⚙️ 5. Comment le Projet Fonctionne (Étape par Étape)

### Étape 1 — Démarrage
```bash
python app.py
```
- Flask démarre sur `http://127.0.0.1:5000`
- `use_reloader=False` : évite les redémarrages intempestifs sur Windows quand les fichiers JSON sont écrits.

### Étape 2 — Chargement des Données
Le frontend charge les données depuis deux sources :
- **MySQL** : données officielles (professeurs, matières, filières).
- **Fichiers JSON locaux** : données de placement (`filier.json`, `class.json`, `matieres.json`).

Un utilisateur peut aussi **importer des données** via :
- Upload Excel/CSV → traité par Pandas → sauvegardé dans `filier.json`
- Upload image → OCR via Tesseract → données extraites → `filier.json`

### Étape 3 — Lancement du Solveur de Placement (`/run-algorithm`)
```
Frontend -> POST /run-algorithm -> app.py -> subprocess -> exam_greedy.py
```

**Ce que fait `exam_greedy.py`** :
1. Charge les salles (`class.json`) et les filières (`filier.json`).
2. Sépare les étudiants en **2 blocs** : Matin (L1, Ingénieur, Prépa) et Après-midi (L2, L3).
3. Construit un modèle **CP-SAT** :
   - Variables : `x[filiere, salle]` = nb d'étudiants affectés
   - Contraintes HARD :
     - Tous les étudiants placés
     - Capacité salle respectée
     - Exactement 2 filières par salle
     - Occupation >= 70%
     - Équilibre : |f1 - f2| <= 4 étudiants
   - Objectif : minimiser les salles utilisées + regrouper par bâtiment
4. Résout en <= 60 secondes avec 16 workers.
5. Sauvegarde dans `placement.json` ET dans MySQL (`salle_filieres`).

### Étape 4 — Génération de la Surveillance (`/api/generate-surveillance`)
```
Frontend -> POST /api/generate-surveillance -> app.py -> subprocess -> generate_surv_ortools.py
```

**Ce que fait `generate_surv_ortools.py`** :
1. Charge depuis MySQL : professeurs, matières (avec `jour_num`, `has_examen`), salles (`salle_filieres`).
2. Calcule les **slots actifs** (Matin1, Matin2, AprèsMidi1, AprèsMidi2) par jour et par salle.
3. Identifie les **profs obligatoires** par jour (ceux dont la matière est examinée ce jour).
4. Construit un modèle **CP-SAT** avec :
   - Variables : `x[prof, jour, salle, slot]` = 1 si prof surveille cette salle ce slot
   - Contraintes HARD :
     - Exactement 2 profs par slot/salle
     - Charge totale <= `charge_surv` (jamais dépassée)
     - Un prof ne peut pas être dans 2 salles simultanément
     - All-or-None : si un prof fait le matin, il fait TOUTES les sessions du matin
   - Contraintes SOFT (pénalités) :
     - Présence obligatoire aux jours de matière (pénalité 1,000,000 si absent)
     - Priorité aux profs à forte charge (pénalité différentielle)
   - Post-processing glouton : remplit les slots encore incomplets
5. Sauvegarde dans `surveillance_cache.json`.

### Étape 5 — Affichage du Dashboard
```
Frontend -> GET /api/surveillance-stats -> app.py -> lit surveillance_cache.json -> JSON -> Frontend
```

- Le dashboard lit `surveillance_cache.json` (si existe) pour éviter de recalculer.
- L'utilisateur peut forcer un recalcul avec `?force=1`.
- L'interface affiche :
  - Par salle et par jour : les professeurs assignés avec leur charge restante.
  - Récapitulatif des charges (utilisées / totales).
  - Logs d'emprunts (profs appelés d'un autre jour).

---

## 🗄️ 6. Schéma de la Base de Données

```
professeur           filaire (filière)
├── id_professeur    ├── id_filaire
├── nom_prenom       ├── nom_filaire
├── grade            ├── abreviation_filaire
└── charge_surv      └── annee

matiere                      salle_filieres
├── id_matiere               ├── salle_name
├── nom_matiere              ├── type_session (matin/apmidi)
├── id_professeur (FK)       ├── id_filiere1 (FK)
├── id_filaire (FK)          └── id_filiere2 (FK)
├── jour_num (1-6)
├── has_ds (0/1)             emploi_du_temps
└── has_examen (0/1)         ├── filiere_id (FK)
                             ├── matiere_id (FK)
                             ├── prof_id (FK)
                             ├── jour (Enum)
                             ├── heure_debut / heure_fin
                             ├── salle
                             └── type_session (CM/TD/TP)
```

---

## 🚀 7. Résumé du Flux Complet

```
Données institutionnelles (MySQL / Excel / OCR)
            |
    Filières + Salles + Professeurs
            |
  ┌─────────────────────────────────┐
  │   CP-SAT Solver (OR-Tools)      │
  │   exam_greedy.py                │
  │   -> Placement étudiant/salle  │
  └────────────┬────────────────────┘
               |
         placement.json
         salle_filieres (MySQL)
               |
  ┌─────────────────────────────────┐
  │   CP-SAT Solver (OR-Tools)      │
  │   generate_surv_ortools.py      │
  │   -> Attribution surveillance  │
  └────────────┬────────────────────┘
               |
       surveillance_cache.json
               |
     Dashboard (report.html)
     Visualisation temps réel
```

---

## ✅ 8. Pour Lancer le Projet

```powershell
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Créer la table emploi du temps (si besoin)
python create_emploi.py

# 3. Lancer le serveur
python app.py

# 4. Ouvrir le navigateur sur http://127.0.0.1:5000
```

> [!IMPORTANT]
> MySQL doit être démarré avec la base `gestion_examens_s1` importée depuis `gestion_examens_s1.sql`.

> [!NOTE]
> Tesseract OCR doit être installé séparément sur Windows et ajouté au PATH système pour que la fonctionnalité d'import par image fonctionne.
