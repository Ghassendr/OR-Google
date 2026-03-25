# OR-Google Project Instructions

## Prerequisites
- **Python 3.x** installed on your system.
- **Tesseract OCR**: Since this project uses `pytesseract` for Optical Character Recognition (OCR) from images, you must have Tesseract OCR installed on your Windows system (download the installer from the official Tesseract GitHub repository and add it to your system PATH).

## Setup & Running the Application

1. **Open your terminal** (e.g., PowerShell, Command Prompt, or VS Code terminal) and navigate to the project directory:
   ```powershell
   cd C:\Users\lasis\Desktop\OR-Google
   ```

2. **Install the required Python packages**:
   Install all the dependencies listed in the `requirements.txt` file by running:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Run the Flask application**:
   Start the backend server by executing:
   ```powershell
   python app.py
   ```

4. **Access the Application**:
   Once the server is running, open a web browser and go to:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)
   This will serve the `report.html` visualization dashboard.

## Overview of Important Files
- `app.py`: The main Flask server application handling API routes and serving the HTML.
- `report.html`: The frontend user interface of the application.
- `exam_greedy.py`, `exam_placement.py`, `exam_calendar.py`: Scripts containing algorithms for exam placement and scheduling (utilizing OR-Tools).
- `requirements.txt`: List of required Python libraries (Flask, Flask-Cors, pandas, openpyxl, pytesseract, Pillow, ortools).
