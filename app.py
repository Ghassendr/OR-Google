from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import subprocess
import pandas as pd
import json
import pytesseract
from PIL import Image

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration for Tesseract (User might need to adjust this path)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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
        return jsonify({'filiers': filiers, 'matieres': matieres})
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
        # OCR logic
        text = pytesseract.image_to_string(Image.open(path))
        
        # Heuristic parsing: look for lines like "Filiere : X (N étudiants)"
        # This is highy dependent on the photo quality.
        new_filiers = []
        for line in text.split('\n'):
            if line.strip():
                # Just a simple example: "NOM 56"
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
        # Fallback for missing Tesseract
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
        
        # Expected columns: "Filiere", "Effectif", "Niveau"
        # If columns don't match, we try to guess or use the first two
        if 'Filiere' not in df.columns:
            df.columns = ['Filiere', 'Effectif'] + list(df.columns[2:])
            
        data = df[['Filiere', 'Effectif']].to_dict(orient='records')
        # Add Niveau if present
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
    algo = request.json.get('algorithm', 'greedy') # 'greedy' or 'sat'
    script = 'exam_greedy.py' if algo == 'greedy' else 'exam_placement.py'
    
    try:
        result = subprocess.run(['python', script], capture_output=True, text=True, check=True)
        return jsonify({'status': 'success', 'output': result.stdout})
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'message': e.stderr, 'output': e.stdout}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
