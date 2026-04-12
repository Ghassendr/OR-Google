from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import functools
import os
import subprocess
import pandas as pd
import json
import pytesseract
from PIL import Image

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    mysql = None
    Error = Exception

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'issat_sousse_2026_super_secret_key')
CORS(app, supports_credentials=True)


UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return send_from_directory('.', 'report.html')

@app.route('/get-data', methods=['GET'])
def get_data():
    try:
        # Load filiers and matieres from JSON (backup or as source if DB not yet primary)
        # However, for rooms, we now use the DB table 'salle'
        with open('filier.json', 'r', encoding='utf-8') as f:
            filiers = json.load(f)
        with open('matieres.json', 'r', encoding='utf-8') as f:
            matieres = json.load(f)
        
        rooms = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT name AS Salle, capacity AS CapaciteTotal, sous_cap1 AS SousCapacite1, sous_cap2 AS SousCapacite2 FROM salle ORDER BY name")
            rooms = cursor.fetchall()
            cursor.close()
            conn.close()
        except:
            # Fallback to local class.json if DB fails
            if os.path.exists('class.json'):
                with open('class.json', 'r', encoding='utf-8') as f:
                    rooms = json.load(f)
                    
        return jsonify({'filiers': filiers, 'matieres': matieres, 'rooms': rooms})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_db_connection():
    if mysql is None:
        raise RuntimeError('mysql.connector introuvable, installez mysql-connector-python')

    cfg = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'gestion_examens_s1'),
        'charset': 'utf8mb4'
    }
    return mysql.connector.connect(**cfg)



# --- Auth Decorators ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Non authentifié'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'ADMIN':
            return jsonify({'error': 'Accès administrateur requis'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/prof', methods=['GET'])
def prof_page():
    return send_from_directory('.', 'prof.html')

@app.route('/login-page', methods=['GET'])
def login_page():
    return send_from_directory('.', 'login.html')

@app.route('/register-page', methods=['GET'])
def register_page():
    return send_from_directory('.', 'register.html')

@app.route('/import-page', methods=['GET'])
@admin_required
def import_page():
    return send_from_directory('.', 'import.html')

# --- Auth Routes ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username et password requis'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT u.*, p.nom_prenom FROM user u LEFT JOIN professeur p ON u.prof_id = p.id_professeur WHERE u.username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['prof_id'] = user['prof_id']
            session['full_name'] = user['nom_prenom'] if user['nom_prenom'] else user['username']
            
            return jsonify({
                'status': 'success',
                'user': {
                    'username': user['username'],
                    'role': user['role'],
                    'full_name': session['full_name']
                }
            })
        
        return jsonify({'error': 'Identifiants invalides'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/professors/unlinked', methods=['GET'])
def get_unlinked_professors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Select professors who don't have a linked user account
        cursor.execute("""
            SELECT p.id_professeur AS id, p.nom_prenom AS name, p.grade 
            FROM professeur p 
            LEFT JOIN user u ON p.id_professeur = u.prof_id 
            WHERE u.id IS NULL 
            ORDER BY p.nom_prenom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    grade = data.get('grade')
    
    prof_id = data.get('prof_id')
    
    if not username or not password or (not full_name and not prof_id):
        return jsonify({'error': 'Username, password et (nom complet ou professeur existant) sont requis'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if user exists
        cursor.execute("SELECT id FROM user WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Ce nom d\'utilisateur est déjà pris'}), 400
            
        # 1. Determine professor linkage
        prof_id = data.get('prof_id')
        
        if prof_id:
            # Check if this professor already has an account
            cursor.execute("SELECT id FROM user WHERE prof_id = %s", (prof_id,))
            if cursor.fetchone():
                return jsonify({'error': 'Ce professeur a déjà un compte utilisateur'}), 400
            # Ensure professor exists
            cursor.execute("SELECT id_professeur FROM professeur WHERE id_professeur = %s", (prof_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Professeur introuvable'}), 404
        else:
            # Create new professor record
            if not full_name:
                return jsonify({'error': 'Le nom complet est requis pour un nouveau professeur'}), 400
            cursor.execute(
                "INSERT INTO professeur (nom_prenom, grade, charge_surv) VALUES (%s, %s, 0)",
                (full_name, grade if grade else '')
            )
            prof_id = cursor.lastrowid
        
        # 2. Create user account
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO user (username, password_hash, role, prof_id) VALUES (%s, %s, 'PROFESSOR', %s)",
            (username, password_hash, prof_id)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Inscription réussie !'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/me', methods=['GET'])
def get_me():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user': {
                'id': session['user_id'],
                'username': session['username'],
                'role': session['role'],
                'prof_id': session['prof_id'],
                'full_name': session['full_name']
            }
        })
    return jsonify({'logged_in': False}), 200

# --- Update Routes ---
@app.route('/api/professors/update', methods=['POST'])
@login_required
def update_professor():
    data = request.json
    prof_id = data.get('id')
    
    # Professors can only update themselves, Admins can update anyone
    if session['role'] != 'ADMIN' and str(session['prof_id']) != str(prof_id):
        return jsonify({'error': 'Permission refusée'}), 403
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Admin can update everything, Prof can update self
        # Fetch current data first to prevent NULL overrides
        cursor.execute("SELECT nom_prenom, grade, charge_surv FROM professeur WHERE id_professeur = %s", (prof_id,))
        current = cursor.fetchone()
        if not current:
            conn.close()
            return jsonify({'error': 'Professeur introuvable'}), 404

        full_name = data.get('full_name') or current['nom_prenom']
        grade = data.get('grade') or current['grade']
        charge = data.get('charge')
        if charge is None:
            charge = current['charge_surv']

        if session['role'] == 'ADMIN':
            cursor.execute(
                "UPDATE professeur SET nom_prenom = %s, grade = %s, charge_surv = %s WHERE id_professeur = %s",
                (full_name, grade, charge, prof_id)
            )
        else:
            # Professors can't change their own charge
            cursor.execute(
                "UPDATE professeur SET nom_prenom = %s, grade = %s WHERE id_professeur = %s",
                (full_name, grade, prof_id)
            )
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/matieres/update', methods=['POST'])
@login_required
def update_matiere():
    data = request.json
    matiere_id = data.get('id')
    has_ds = data.get('ds')
    has_examen = data.get('examen')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check ownership if not admin
        if session['role'] != 'ADMIN':
            cursor.execute("SELECT id_professeur FROM matiere WHERE id_matiere = %s", (matiere_id,))
            matiere = cursor.fetchone()
            if not matiere or str(matiere['id_professeur']) != str(session['prof_id']):
                return jsonify({'error': 'Ce n\'est pas votre matière'}), 403
        
        cursor.execute(
            "UPDATE matiere SET has_ds = %s, has_examen = %s WHERE id_matiere = %s",
            (1 if has_ds else 0, 1 if has_examen else 0, matiere_id)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/professors', methods=['GET'])
def api_professors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_professeur AS id, nom_prenom AS full_name, grade, charge_surv AS charge, 1 AS status FROM professeur ORDER BY nom_prenom LIMIT 1000")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'professors': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/matieres', methods=['GET'])
def api_matieres():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT m.id_matiere AS id, m.code_matiere AS code, m.nom_matiere AS nom, m.id_professeur AS id_professeur, 
                   COALESCE(m.has_ds, 0) AS ds, COALESCE(m.has_examen, 0) AS examen, 
                   m.id_filaire AS filiere_id, m.jour_num AS jour, p.nom_prenom AS prof_nom, p.grade AS prof_grade,
                   f.nom_filaire AS filiere, f.abreviation_filaire AS filiere_abrev,
                   f.annee AS filiere_annee
            FROM matiere m
            LEFT JOIN professeur p ON m.id_professeur = p.id_professeur
            LEFT JOIN filaire f ON m.id_filaire = f.id_filaire
            ORDER BY m.nom_matiere
            LIMIT 1000
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'matieres': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/filieres', methods=['GET'])
def api_filieres():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id_filaire AS id, nom_filaire AS nom, abreviation_filaire AS abrevation, code_filaire AS code, annee FROM filaire ORDER BY nom_filaire LIMIT 1000')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'filieres': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable', methods=['GET'])
def api_timetable():
    try:
        filiere_id = request.args.get('filiere_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = '''
            SELECT e.id, e.filiere_id, e.matiere_id, e.prof_id, e.jour, 
                   e.heure_debut, 
                   e.heure_fin, 
                   e.salle, e.type_session,
                   m.nom_matiere as matiere_nom, p.nom_prenom as prof_nom
            FROM emploi_du_temps e
            JOIN matiere m ON e.matiere_id = m.id_matiere
            LEFT JOIN professeur p ON e.prof_id = p.id_professeur
        '''
        
        if filiere_id:
            query += " WHERE e.filiere_id = %s"
            cursor.execute(query, (filiere_id,))
        else:
            cursor.execute(query)
            
        rows = cursor.fetchall() or []
        
        for r in rows:
            if r['heure_debut']:
                r['heure_debut'] = str(r['heure_debut'])[:5]
            if r['heure_fin']:
                r['heure_fin'] = str(r['heure_fin'])[:5]
        
        cursor.close()
        conn.close()
        return jsonify({'timetable': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/salle-filieres', methods=['GET'])
def api_salle_filieres():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT sf.salle_name, sf.type_session, 
                   f1.nom_filaire as filiere1_nom, 
                   f2.nom_filaire as filiere2_nom
            FROM salle_filieres sf
            LEFT JOIN filaire f1 ON sf.id_filiere1 = f1.id_filaire
            LEFT JOIN filaire f2 ON sf.id_filiere2 = f2.id_filaire
            ORDER BY sf.type_session DESC, sf.salle_name ASC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'data': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendrier/<int:jour_num>', methods=['GET'])
def api_calendrier(jour_num):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
                m.nom_matiere, 
                m.id_filaire,
                f.nom_filaire,
                sf.salle_name, 
                sf.type_session
            FROM matiere m
            JOIN filaire f ON m.id_filaire = f.id_filaire
            JOIN salle_filieres sf ON (sf.id_filiere1 = m.id_filaire OR sf.id_filiere2 = m.id_filaire)
            WHERE m.jour_num = %s AND m.has_examen = 1
        ''', (jour_num,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        rooms = {}
        for r in rows:
            s_name = r['salle_name']
            if s_name not in rooms:
                rooms[s_name] = {'salle': s_name, 'matin': {'slot1': [], 'slot2': []}, 'apmidi': {'slot1': [], 'slot2': []}}
                
        filiere_mats = {}
        for r in rows:
            key = (r['salle_name'], r['type_session'], r['id_filaire'], r['nom_filaire'])
            if key not in filiere_mats:
                filiere_mats[key] = []
            filiere_mats[key].append(r['nom_matiere'])
            
        for (s_name, t_session, f_id, f_nom), mat_list in filiere_mats.items():
            mat1 = mat_list[0] if len(mat_list) > 0 else None
            mat2 = mat_list[1] if len(mat_list) > 1 else None
            
            if mat1:
                rooms[s_name][t_session]['slot1'].append({'filiere': f_nom, 'matiere': mat1})
            if mat2:
                rooms[s_name][t_session]['slot2'].append({'filiere': f_nom, 'matiere': mat2})

        final_rooms = []
        for s_name, data in rooms.items():
            has_data = len(data['matin']['slot1']) > 0 or len(data['matin']['slot2']) > 0 or \
                       len(data['apmidi']['slot1']) > 0 or len(data['apmidi']['slot2']) > 0
            if has_data:
                final_rooms.append(data)

        final_rooms.sort(key=lambda x: x['salle'])
        return jsonify({'data': final_rooms})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/surveillance-stats', methods=['GET'])
def api_surveillance_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get Room assignments
        cursor.execute("SELECT salle_name, type_session, id_filiere1, id_filiere2 FROM salle_filieres")
        rooms = cursor.fetchall()
        
        # 2. Get Exam counts per filiere and day
        cursor.execute('''
            SELECT id_filaire, jour_num, COUNT(*) as exam_count 
            FROM matiere 
            WHERE has_examen = 1 
            GROUP BY id_filaire, jour_num
        ''')
        exam_data = cursor.fetchall()
        
        # Organize exam counts: {filiere_id: {jour_num: count}}
        filiere_counts = {}
        for row in exam_data:
            fid = row['id_filaire']
            jno = row['jour_num']
            if fid not in filiere_counts: filiere_counts[fid] = {}
            filiere_counts[fid][jno] = row['exam_count']
            
        # 3. Calculate per room
        results = []
        for r in rooms:
            room_name = r['salle_name']
            id1 = r['id_filiere1']
            id2 = r['id_filiere2']
            
            daily_stats = {}
            total_profs = 0
            
            for day in range(1, 7): # Lundi to Samedi
                c1 = filiere_counts.get(id1, {}).get(day, 0) if id1 else 0
                c2 = filiere_counts.get(id2, {}).get(day, 0) if id2 else 0
                
                # Max slots used in the room that day
                slots = max(c1, c2)
                profs_needed = slots * 2
                
                day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'][day-1]
                daily_stats[day_name] = profs_needed
                total_profs += profs_needed
                
            results.append({
                'salle': room_name,
                'session': r['type_session'],
                'total_profs': total_profs,
                'daily': daily_stats,
                'building': room_name[0]
            })
            
        cursor.close()
        conn.close()
        
        results.sort(key=lambda x: (x['building'], x['salle']))
        return jsonify({'data': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-filiers', methods=['POST'])
@app.route('/save-data', methods=['POST'])
@admin_required
def save_data():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Pre-fetch all filières to do smart matching in Python (more flexible than SQL)
        cursor.execute("SELECT id_filaire, abreviation_filaire, nom_filaire, annee FROM filaire")
        db_filiaires = cursor.fetchall()

        def normalize(s):
            if not s: return ""
            # Ultra-fuzzy: no spaces, underscores, dashes, or L_ prefix
            return s.replace('L_', '').replace('_', '').replace(' ', '').replace('-', '').lower().strip()

        def find_best_match(import_name, import_level):
            name_norm = normalize(import_name)
            
            db_annee = '1ERE'
            lvl_lower = import_level.lower()
            if '2eme' in lvl_lower: db_annee = '2EME'
            elif '3eme' in lvl_lower: db_annee = '3EME'
            
            # Sub-function for Master prefix stripping
            def remove_master_prefix(n):
                if n.startswith('mr') or n.startswith('mp'):
                    return n[2:]
                return n

            for f in db_filiaires:
                # Normal filter by year, UNLESS it's a 'master' import. 
                # Masters in DB are 1ERE or 2EME, so we bypass strict year matching if import level says 'master'
                if 'master' not in lvl_lower and f['annee'] != db_annee: 
                    continue
                
                # If it's a master import, ONLY match against Master DB entries
                if 'master' in lvl_lower and 'MASTER' not in str(f.get('type_filaire', '')):
                    # Fallback check since type_filaire wasn't fetched in the original query!
                    # We will just allow it to match based on abbreviation.
                    pass

                db_abrev_norm = normalize(f['abreviation_filaire'])
                db_nom_norm = normalize(f['nom_filaire'])
                
                # Check 0: Explicit M2 routing
                if 'master' in lvl_lower and name_norm.endswith('2'):
                    db_abrev_no2 = name_norm.replace('2', '')
                    if db_abrev_norm == db_abrev_no2 and f['annee'] == '2EME': return f['id_filaire']
                
                # Check 1: Exact Normalized abbreviation
                if name_norm == db_abrev_norm: 
                    return f['id_filaire']
                
                # Check 2: Master abbreviation matching (strip MR/MP)
                if 'master' in lvl_lower:
                    if remove_master_prefix(name_norm) == db_abrev_norm: 
                        return f['id_filaire']
                
                # Check 3: Full name containment (with collision safeguard)
                if name_norm in db_nom_norm or db_nom_norm in name_norm:
                    if len(name_norm) <= 3 and len(db_nom_norm) > 5 and name_norm != db_abrev_norm:
                        pass
                    else:
                        return f['id_filaire']
                
                # Check 4: Hardcoded common variants
                if name_norm == 'preparatoire' or name_norm == 'cyclepreparatoire':
                    if db_abrev_norm == 'prep': return f['id_filaire']
                if (name_norm == 'energ' or name_norm == 'lenerg') and db_abrev_norm == 'eng': return f['id_filaire']
                if name_norm == 'ingenieur' and db_abrev_norm == 'ing': return f['id_filaire']
                if name_norm == '2gl' and db_abrev_norm == 'gl': return f['id_filaire']
                if name_norm == '3gl' and db_abrev_norm == 'glal': return f['id_filaire']
                if name_norm == 'mppai' and db_abrev_norm == 'pai': return f['id_filaire']
                if name_norm == 'mrsm' and db_abrev_norm == 'mrgmsm': return f['id_filaire']
                if name_norm == 'mrmm' and db_abrev_norm == 'mrgmmm': return f['id_filaire']

            
            return None

        if 'filiers' in data:
            # Reset all to 0 to ensure we don't keep stale data
            cursor.execute("UPDATE filaire SET effectif = 0")
            
            match_count = 0
            for item in data['filiers']:
                nom = item.get('Filiere', '')
                niv = item.get('Niveau', '')
                eff = item.get('Effectif', 0)
                
                # Desable Masters
                if 'master' in niv.lower() or 'master' in str(nom).lower():
                    continue
                    
                try:
                    eff = int(eff)
                except:
                    eff = 0
                
                matched_id = find_best_match(nom, niv)
                if matched_id:
                    cursor.execute("UPDATE filaire SET effectif = %s WHERE id_filaire = %s", (eff, matched_id))
                    match_count += 1
                else:
                    print(f"  [Sync Auto-Insert] Création de la filière manquante: {nom} ({niv})")
                    niv_lower = niv.lower()
                    
                    # Deduce Year
                    db_annee = '1ERE'
                    if '2eme' in niv_lower: db_annee = '2EME'
                    elif '3eme' in niv_lower: db_annee = '3EME'
                    
                    # Deduce Type
                    nom_lower = nom.lower()
                    type_fil = 'LICENCE'
                    if 'master' in niv_lower or nom_lower.startswith('mr') or nom_lower.startswith('mp'):
                        if 'recherche' in nom_lower or nom_lower.startswith('mr'): type_fil = 'MASTER_RECHERCHE'
                        else: type_fil = 'MASTER_PRO'
                        # Masters in 2ème if specifically trailing with 2
                        if '2' in nom_lower and db_annee == '1ERE': db_annee = '2EME'
                    elif 'ing' in nom_lower or 'gl' in nom_lower or 'a1' in nom_lower: type_fil = 'INGENIEUR'
                    elif 'prep' in nom_lower: type_fil = 'PREPA'
                    
                    cursor.execute(
                        "INSERT INTO filaire (abreviation_filaire, nom_filaire, type_filaire, annee, effectif) VALUES (%s, %s, %s, %s, %s)",
                        (nom, nom, type_fil, db_annee, eff)
                    )
                    # Add newly inserted element to our runtime list so it can be matched if duplicated
                    db_filiaires.append({
                        'id_filaire': cursor.lastrowid,
                        'abreviation_filaire': nom,
                        'nom_filaire': nom,
                        'annee': db_annee,
                        'type_filaire': type_fil
                    })
                    match_count += 1
            
            print(f"  [Sync] Terminé: {match_count}/{len(data['filiers'])} filières synchronisées (incluant insertions).")

            
            # Heritage: keep JSON for legacy fallback
            with open('filier.json', 'w', encoding='utf-8') as f:
                json.dump(data['filiers'], f, indent=4, ensure_ascii=False)

        if 'matieres' in data:
            with open('matieres.json', 'w', encoding='utf-8') as f:
                json.dump(data['matieres'], f, indent=4, ensure_ascii=False)
                
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Synchronisation terminée avec succès.'})
    except Exception as e:
        import traceback
        with open('error_log.txt', 'a') as f:
            f.write(traceback.format_exc() + "\n")
        
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/upload-ocr', methods=['POST'])
def upload_ocr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    try:
        text = pytesseract.image_to_string(Image.open(path))
        
        new_filiers = []
        for line in text.split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    name = " ".join(parts[:-1])
                    new_filiers.append({"Filiere": name, "Effectif": int(parts[-1]), "Niveau": "Import OCR"})
        
        if new_filiers:
            with open('filier.json', 'w', encoding='utf-8') as f:
                json.dump(new_filiers, f, indent=4, ensure_ascii=False)
            return jsonify({'message': f'OCR réussi: {len(new_filiers)} filières extraites.'})
        
        return jsonify({'text': text, 'message': 'OCR terminé mais aucune donnée structurée trouvée. Vérifiez le texte brut.'})
    except Exception as e:
        return jsonify({'error': f"Erreur OCR: {str(e)}. Vérifiez que Tesseract est installé."}), 500

@app.route('/upload-excel', methods=['POST'])
def upload_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
        
        if 'Filiere' not in df.columns:
            df.columns = ['Filiere', 'Effectif'] + list(df.columns[2:])
            
        data = df[['Filiere', 'Effectif']].to_dict(orient='records')
        if 'Niveau' in df.columns:
            for i, d in enumerate(data):
                d['Niveau'] = str(df.iloc[i]['Niveau'])
        
        with open('filier.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return jsonify({'message': f'Import réussi: {len(data)} lignes chargées.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Distribution Management ---

@app.route('/api/distribution/save', methods=['POST'])
@admin_required
def save_distribution():
    data = request.json
    name = data.get('name', 'Nouveau Planning')
    content = data.get('data')
    params = data.get('params', {})
    
    if not content:
        return jsonify({'error': 'Aucune donnée de distribution'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO distribution_history (name, data_json, params_json) VALUES (%s, %s, %s)",
            (name, json.dumps(content), json.dumps(params))
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Distribution sauvegardée dans l\'historique.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/distribution/history', methods=['GET'])
@admin_required
def get_distribution_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, created_at, is_active FROM distribution_history ORDER BY created_at DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/distribution/load/<int:dist_id>', methods=['GET'])
@admin_required
def load_distribution(dist_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM distribution_history WHERE id = %s", (dist_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Distribution introuvable'}), 404
            
        data = json.loads(row['data_json'])
        # Also write to placement.json for legacy algorithm compatibility
        with open('placement.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return jsonify({'status': 'success', 'data': data, 'params': json.loads(row['params_json'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/distribution/activate', methods=['POST'])
@admin_required
def activate_distribution():
    data = request.json
    dist_id = data.get('id')
    content = data.get('data') # If id is not provided, activate current data
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Reset all active states
        cursor.execute("UPDATE distribution_history SET is_active = 0")
        
        if dist_id:
            cursor.execute("UPDATE distribution_history SET is_active = 1 WHERE id = %s", (dist_id,))
        elif content:
            # Create a new active entry if none exists for this current state
            cursor.execute(
                "INSERT INTO distribution_history (name, data_json, params_json, is_active) VALUES (%s, %s, %s, 1)",
                ("Distribution Activee", json.dumps(content), "{}")
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Distribution activée avec succès.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/distribution/active', methods=['GET'])
def get_active_distribution():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM distribution_history WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Aucune distribution active'}), 404
            
        data = json.loads(row['data_json'])
        return jsonify({'status': 'success', 'data': data, 'params': json.loads(row['params_json'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/run-algorithm', methods=['POST'])
@admin_required
def run_algorithm():
    algo = request.json.get('algorithm', 'greedy') 
    script = 'exam_greedy.py' if algo == 'greedy' else 'exam_placement.py'
    
    # Store config in a subfolder to avoid triggering Flask reloader
    if not os.path.exists('data'): os.makedirs('data')
    config_path = os.path.join('data', 'solver_config.json')

    params = request.json.get('params')
    if params:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=4)
    elif os.path.exists(config_path):
        try: os.remove(config_path)
        except: pass

    target = request.json.get('target', 'all')
    cmd = ['python', script]
    if target in ['matin', 'apmidi']:
        cmd.append(target)

    try:
        # Run with a generous timeout to prevent connection reset
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
        return jsonify({'status': 'success', 'output': result.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'L\'algorithme a pris trop de temps (timeout 5 min).'}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'message': e.stderr or 'Erreur interne de l\'algorithme', 'output': e.stdout}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
