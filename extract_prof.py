import mysql.connector

conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='', database='gestion_examens_s1')
c = conn.cursor(dictionary=True)
c.execute('SELECT id_professeur, nom_prenom, grade, charge_surv FROM professeur ORDER BY nom_prenom')
rows = c.fetchall()

with open('prof_list.md', 'w', encoding='utf-8') as f:
    f.write('# Liste des Professeurs (gestion_examens_s1)\n\n')
    f.write('| ID | Nom & Prénom | Grade | Charge |\n')
    f.write('|---|---|---|---|\n')
    for r in rows:
        f.write(f"| {r['id_professeur']} | {r['nom_prenom']} | {r['grade']} | {r['charge_surv']}h |\n")
