from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
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
CORS(app)


UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return send_from_directory('.', 'report.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

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


@app.route('/prof', methods=['GET'])
def prof_page():
    return send_from_directory('.', 'prof.html')


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
        # Check if the optimized cache exists - use it by default if available
        # Pass ?force=1 to bypass cache and use the greedy fallback
        force = request.args.get('force', '0') == '1'
        if not force and os.path.exists('surveillance_cache.json'):
            with open('surveillance_cache.json', 'r', encoding='utf-8') as f:
                cached = json.load(f)
                return jsonify({'data': cached['data'], 'source': 'ortools'})
                
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_professeur as id, nom_prenom as full_name, grade, charge_surv FROM professeur")
        profs_db = cursor.fetchall()
        
        cursor.execute("SELECT id_matiere, nom_matiere, jour_num, id_professeur, has_examen FROM matiere WHERE has_examen=1 AND jour_num IS NOT NULL")
        matieres = cursor.fetchall()
        
        cursor.execute("SELECT salle_name, type_session, id_filiere1, id_filiere2 FROM salle_filieres")
        salle_filieres = cursor.fetchall()
        
        cursor.execute("SELECT id_filaire, jour_num, COUNT(*) as exam_count FROM matiere WHERE has_examen = 1 AND jour_num IS NOT NULL GROUP BY id_filaire, jour_num")
        exam_data = cursor.fetchall()
        
        cursor.close()
        conn.close()

        filiere_counts = {}
        for row in exam_data:
            fid = row['id_filaire']
            jno = row['jour_num']
            if fid not in filiere_counts: filiere_counts[fid] = {}
            filiere_counts[fid][jno] = row['exam_count']

        prof_state = {}
        for p in profs_db:
            if p['charge_surv'] is None: p['charge_surv'] = 0
            prof_state[p['id']] = {
                'full_name': p['full_name'],
                'grade': p['grade'],
                'total_charges': p['charge_surv'],
                'reste_charges': p['charge_surv'],
                'jours_obligatoires': set()
            }

        for m in matieres:
            pid = m['id_professeur']
            if pid in prof_state and m['jour_num']:
                prof_state[pid]['jours_obligatoires'].add(m['jour_num'])

        # ── TRI GLOBAL PAR CHARGE DESC ──────────────────────────────────────
        # Les profs avec plus de charge_surv sont traités en priorité.
        # Cela évite que des profs à faible charge (ex: 6) soient sur-utilisés
        # pendant que des profs à forte charge (ex: 10) restent sous-utilisés.
        def sort_by_charge_desc(pid_list):
            return sorted(pid_list, key=lambda pid: -prof_state[pid]['total_charges'])

        available_pool = []
        global_pool = sort_by_charge_desc([p['id'] for p in profs_db if prof_state[p['id']]['total_charges'] > 0])
        
        all_rooms = list(set(r['salle_name'] for r in salle_filieres))
        results_by_room = {room: {'salle': room, 'total_profs_set': set(), 'daily': {}, 'building': room[0]} for room in all_rooms}

        for day in range(1, 7):
            day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'][day-1]
            
            room_configs = {}
            for r in salle_filieres:
                s_name = r['salle_name']
                t_ses = r['type_session']
                if s_name not in room_configs:
                    room_configs[s_name] = {'matin_slots': 0, 'apmidi_slots': 0}
                
                c1 = filiere_counts.get(r['id_filiere1'], {}).get(day, 0) if r['id_filiere1'] else 0
                c2 = filiere_counts.get(r['id_filiere2'], {}).get(day, 0) if r['id_filiere2'] else 0
                max_exams = max(c1, c2)
                
                if t_ses == 'matin':
                    room_configs[s_name]['matin_slots'] = max(room_configs[s_name]['matin_slots'], min(max_exams, 2))
                else:
                    room_configs[s_name]['apmidi_slots'] = max(room_configs[s_name]['apmidi_slots'], min(max_exams, 2))
                    
            active_rooms = {s: v for s, v in room_configs.items() if v['matin_slots'] > 0 or v['apmidi_slots'] > 0}

            # Profs obligatoires ce jour, triés par charge DESC
            profs_of_day = sort_by_charge_desc([
                pid for pid in prof_state
                if day in prof_state[pid]['jours_obligatoires']
                and prof_state[pid]['reste_charges'] > 0
            ])
            
            for room, slots in active_rooms.items():
                matin_s = slots['matin_slots']
                apmidi_s = slots['apmidi_slots']
                total_s = matin_s + apmidi_s
                
                sessions_needed = total_s * 2 # 2 profs per session
                max_slots_per_prof_here = total_s
                room_assigned_profs = {}
                
                while sessions_needed > 0:
                    assigned_prof = None
                    
                    # 1. D'abord: profs déjà dans cette salle avec charge restante (stabilité)
                    for pid in sort_by_charge_desc(list(room_assigned_profs.keys())):
                        if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs[pid] < max_slots_per_prof_here:
                            assigned_prof = pid
                            break
                    
                    # 2. Ensuite: profs obligatoires du jour, triés par charge DESC
                    if not assigned_prof:
                        for pid in profs_of_day:
                            if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs.get(pid, 0) < max_slots_per_prof_here:
                                assigned_prof = pid
                                break
                                
                    # 3. Ensuite: pool disponible, trié par charge DESC
                    if not assigned_prof:
                        for pid in sort_by_charge_desc(available_pool):
                            if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs.get(pid, 0) < max_slots_per_prof_here:
                                assigned_prof = pid
                                break
                                
                    # 4. Enfin: pool global (tous les profs), trié par charge DESC
                    if not assigned_prof:
                        for pid in global_pool:
                            if prof_state[pid]['reste_charges'] > 0 and pid not in available_pool and room_assigned_profs.get(pid, 0) < max_slots_per_prof_here:
                                assigned_prof = pid
                                available_pool.append(pid)
                                break
                    
                    if assigned_prof:
                        prof_state[assigned_prof]['reste_charges'] -= 1
                        sessions_needed -= 1
                        room_assigned_profs[assigned_prof] = room_assigned_profs.get(assigned_prof, 0) + 1
                        results_by_room[room]['total_profs_set'].add(assigned_prof)
                    else:
                        break
                        
                results_by_room[room]['daily'][day_name] = {
                   'matin_sessions': matin_s,
                   'apmidi_sessions': apmidi_s,
                   'profs_needed': sum(room_assigned_profs.values()),
                   'profs': [
                       {
                           'full_name': prof_state[pid]['full_name'],
                           'grade': prof_state[pid]['grade'],
                           'charge': f"{count} sess. (Rest: {prof_state[pid]['reste_charges']})"
                       }
                       for pid, count in room_assigned_profs.items()
                   ]
                }

            for pid in profs_of_day:
                if prof_state[pid]['reste_charges'] > 0 and pid not in available_pool:
                    available_pool.append(pid)

        final_results = []
        for room, data in results_by_room.items():
            data['total_profs'] = len(data['total_profs_set'])
            del data['total_profs_set']
            if len(data['daily']) > 0:
                final_results.append(data)
                
        final_results.sort(key=lambda x: (x['building'], x['salle']))
        return jsonify({'data': final_results})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-surveillance', methods=['POST'])
def generate_surveillance():
    import subprocess
    try:
        # Run the solver script. This may take ~60 seconds.
        result = subprocess.run(['python', 'generate_surv_ortools.py'], capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'status': 'success', 'message': 'Planning Parfait généré avec succès !'})
        else:
            return jsonify({'status': 'error', 'message': f'Erreur: {result.stderr}'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
    # use_reloader=False prevents the server from restarting when a file is written (like surveillance_cache.json)
    # which causes ERR_CONNECTION_RESET on Windows
    app.run(debug=True, port=5000, use_reloader=False)
