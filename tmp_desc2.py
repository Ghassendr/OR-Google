import mysql.connector
import os
import json

c=mysql.connector.connect(host=os.getenv('DB_HOST', '127.0.0.1'), user=os.getenv('DB_USER', 'root'), password='', database='gestion_examens_s1')
cr=c.cursor(dictionary=True)
cr.execute('DESCRIBE matiere')
print("--- matiere ---")
for r in cr.fetchall(): print(r)
print("--- emploi_du_temps ---")
try:
    cr.execute('DESCRIBE emploi_du_temps')
    for r in cr.fetchall(): print(r)
except Exception as e: print(e)
