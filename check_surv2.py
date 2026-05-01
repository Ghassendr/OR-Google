import json, mysql.connector, os

conn = mysql.connector.connect(
    host='127.0.0.1', user='root', password='',
    database='gestion_examens_s1', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

cur.execute("SELECT id_professeur as id, nom_prenom as full_name, grade, charge_surv FROM professeur")
profs = {p['id']: p for p in cur.fetchall()}

cur.execute("SELECT id_matiere, nom_matiere, jour_num, id_professeur FROM matiere WHERE has_examen=1 AND jour_num IS NOT NULL")
matieres = cur.fetchall()
cur.close(); conn.close()

# Jours obligatoires par prof
matieres_days = {}
for m in matieres:
    pid = m['id_professeur']
    if pid not in matieres_days:
        matieres_days[pid] = set()
    if m['jour_num']:
        matieres_days[pid].add(m['jour_num'])

# Charge vs jours obligatoires
print("Profs avec forte charge mais peu de jours obligatoires (mauvaise distribution):")
print(f"  {'Nom':<32} {'Charge':<8} {'Jours_oblig':<12} {'Charge_libre'}")
print("  " + "-"*65)
items = []
for pid, p in profs.items():
    charge = p['charge_surv'] or 0
    if charge <= 0: continue
    jours = matieres_days.get(pid, set())
    libre = max(0, charge - len(jours))
    items.append((charge, p['full_name'], charge, len(jours), libre))

items.sort(reverse=True)
for _, nom, charge, nb_jours, libre in items[:30]:
    print(f"  {nom:<32} {charge:<8} {nb_jours:<12} {libre}")
