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
        with open('filier.json', 'r', encoding='utf-8') as f:
            filiers = json.load(f)
        with open('matieres.json', 'r', encoding='utf-8') as f:
            matieres = json.load(f)
        rooms = []
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
        cursor = conn.cursor()
        
        if session['role'] == 'ADMIN':
            # Admin can update everything
            cursor.execute(
                "UPDATE professeur SET nom_prenom = %s, grade = %s, charge_surv = %s WHERE id_professeur = %s",
                (data.get('full_name'), data.get('grade'), data.get('charge'), prof_id)
            )
        else:
            # Prof can only update name/grade maybe? Let's limit for now
            cursor.execute(
                "UPDATE professeur SET nom_prenom = %s, grade = %s WHERE id_professeur = %s",
                (data.get('full_name'), data.get('grade'), prof_id)
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


@app.route('/api/save-filiers', methods=['POST'])
@admin_required
def save_filiers():
    data = request.json
    filiers = data.get('filiers', [])
    if not filiers:
        return jsonify({'error': 'Aucune donnée fournie'}), 400
    try:
        with open('filier.json', 'w', encoding='utf-8') as f:
            json.dump(filiers, f, indent=4, ensure_ascii=False)
        return jsonify({'message': f'{len(filiers)} filières sauvegardées avec succès.'})
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

@app.route('/save-data', methods=['POST'])
def save_data():
    try:
        data = request.json
        if 'filiers' in data:
            with open('filier.json', 'w', encoding='utf-8') as f:
                json.dump(data['filiers'], f, indent=4, ensure_ascii=False)
        if 'matieres' in data:
            with open('matieres.json', 'w', encoding='utf-8') as f:
                json.dump(data['matieres'], f, indent=4, ensure_ascii=False)
        return jsonify({'status': 'success'})
    except Exception as e:
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

@app.route('/run-algorithm', methods=['POST'])
@admin_required
def run_algorithm():
    algo = request.json.get('algorithm', 'greedy') 
    script = 'exam_greedy.py' if algo == 'greedy' else 'exam_placement.py'
    
    params = request.json.get('params')
    if params:
        with open('solver_config.json', 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=4)
    elif os.path.exists('solver_config.json'):
        try:
            os.remove('solver_config.json')
        except:
            pass

    target = request.json.get('target', 'all')

    cmd = ['python', script]
    if target in ['matin', 'apmidi']:
        cmd.append(target)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return jsonify({'status': 'success', 'output': result.stdout})
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'message': e.stderr, 'output': e.stdout}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
