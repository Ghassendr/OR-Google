import mysql.connector
conn = mysql.connector.connect(host='127.0.0.1', user='root', database='gestion_examens_s1')
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT id_filaire, nom_filaire, abreviation_filaire FROM filaire')
for r in cursor.fetchall():
    print(r['id_filaire'], repr(r['nom_filaire']), repr(r['abreviation_filaire']))
