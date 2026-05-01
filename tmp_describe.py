import mysql.connector
import os
import json

c=mysql.connector.connect(host=os.getenv('DB_HOST', '127.0.0.1'), user=os.getenv('DB_USER', 'root'), password='', database='gestion_examens_s1')
cr=c.cursor(dictionary=True)
cr.execute('DESCRIBE professeur')
rows = cr.fetchall()
print(json.dumps(rows, indent=2))
