import requests
import json

def test_api():
    url = "http://127.0.0.1:5000/api/matieres"
    try:
        r = requests.get(url)
        print(f"Status: {r.status_code}")
        data = r.json()
        if 'matieres' in data and len(data['matieres']) > 0:
            print("First item keys:", list(data['matieres'][0].keys()))
            print("First item values:", data['matieres'][0])
        else:
            print("No matieres found or wrong format")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_api()
