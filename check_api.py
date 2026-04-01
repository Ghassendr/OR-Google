import requests
import json

def test_api():
    url = "http://127.0.0.1:5000/api/professors"
    try:
        r = requests.get(url)
        print(f"Status: {r.status_code}")
        print(f"Body: {r.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_api()
