import mysql.connector
conn = mysql.connector.connect(host='127.0.0.1', user='root', password='', database='gestion_examens_s1')
cur = conn.cursor(dictionary=True)
cur.execute('SELECT p.id_professeur, p.nom_prenom, p.charge_surv, COUNT(DISTINCT m.jour_num) as m_days FROM professeur p JOIN matiere m ON p.id_professeur = m.id_professeur WHERE m.has_examen=1 AND m.jour_num IS NOT NULL GROUP BY p.id_professeur')
res = cur.fetchall()
for r in res:
    charge = r['charge_surv'] or 0
    if r['m_days'] * 2 > charge:
        print(f"{r['nom_prenom']}: charge {charge}, m_days {r['m_days']}")
