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
        'database': os.getenv('DB_NAME', 'OR_google_database'),
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
        cursor.execute('SELECT id, full_name, grade, charge, status FROM professeur ORDER BY full_name LIMIT 1000')
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
            SELECT m.id, m.nom, m.id_professeur, p.full_name AS professeur, 
                   f.nom AS filiere, f.abrevation AS filiere_abrev, f.annee AS filiere_annee
            FROM matiere m
            LEFT JOIN professeur p ON m.id_professeur = p.id
            LEFT JOIN filaire f ON m.id_filaire = f.id
            ORDER BY m.nom
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
        cursor.execute('SELECT id, nom, abrevation, annee FROM filaire ORDER BY nom LIMIT 1000')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'filieres': rows})
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
