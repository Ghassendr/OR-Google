"""
exam_calendar.py  –  Planification des examens (2 phases)
==========================================================

Phase 1  : CP-SAT assigne chaque filiere a un creneau (jour, slot)
           en evitant les conflits de capacite.

Phase 2  : Pour chaque creneau occupe, CP-SAT affecte les groupes
           aux salles disponibles (modele independant par creneau).

Contraintes HARD :
  - Ingenieurs / Prepa / Masters  -> creneaux matin  (08h30, 10h15)
  - Licences L1/L2/L3             -> creneaux apres-midi (12h00, 13h45)
  - Occupation salle <= CapaciteTotal - BUFFER
  - <= 2 filieres differentes par salle et par creneau

Contraintes SOFT (dans l'objectif) :
  - Minimiser le nombre de creneaux utilises (compresser le calendrier)
  - Minimiser le nombre de salles par creneau
  - Favoriser l'occupation minimale de 40% (penalite sinon)
  - Regrouper par batiment (K, M, I, J)
"""

import sys, json, math
sys.stdout.reconfigure(encoding='utf-8')
from ortools.sat.python import cp_model
from collections import defaultdict

# ============================================================
# 1. CHARGEMENT
# ============================================================

with open('class.json',       'r', encoding='utf-8') as f:
    rooms_data = json.load(f)
with open('filier.json',      'r', encoding='utf-8') as f:
    filieres_raw = json.load(f)
with open('calendrie_DS.json','r', encoding='utf-8') as f:
    calendar_data = json.load(f)

BUFFER       = 4    # places de securite par salle
MAX_GRP_SIZE = 30   # taille max d'un sous-groupe dans une salle

# ============================================================
# 2. CRENEAUX
# ============================================================

num_days     = len(calendar_data)               # 6
NUM_SLOT_DAY = len(calendar_data[0]['Horaires'])  # 4
MORNING_IDX  = [0, 1]    # 08h30, 10h15
AFTERNOON_IDX= [2, 3]    # 12h00, 13h45
SLOT_LABELS  = ['08h30-09h30', '10h15-11h15', '12h00-13h00', '13h45-14h45']

def slot_global(d, s): return d * NUM_SLOT_DAY + s
NUM_SLOTS = num_days * NUM_SLOT_DAY   # 24

# ============================================================
# 3. FILIERES
# ============================================================

def classify(name, annee_key):
    if annee_key == 'master': return 'morning'
    if 'Ingenieur' in name or 'Cycle_Preparatoire' in name: return 'morning'
    return 'afternoon'

def split_groups(effectif):
    n = max(1, math.ceil(effectif / MAX_GRP_SIZE))
    base, rem = effectif // n, effectif % n
    return [base + (1 if i < rem else 0) for i in range(n)]

filieres = []
for annee_key, annee_val in filieres_raw['annees'].items():
    sub = annee_val.get('programmes', {}) if annee_key == 'master' else annee_val.get('filieres', {})
    for nom, effectif in sub.items():
        if effectif == 0: continue
        cat = classify(nom, annee_key)
        filieres.append({
            'id'    : len(filieres),
            'name'  : nom,
            'size'  : effectif,
            'annee' : annee_key,
            'cat'   : cat,
            'groups': split_groups(effectif),
        })

print(f"=== PLANIFICATION DES EXAMENS ===")
print(f"Filieres chargees : {len(filieres)}")
print(f"  - Matin  (Ing/Prepa/Master) : {sum(1 for f in filieres if f['cat']=='morning')} filieres "
      f"| {sum(f['size'] for f in filieres if f['cat']=='morning')} etudiants")
print(f"  - Apres-midi (Licences L1-3): {sum(1 for f in filieres if f['cat']=='afternoon')} filieres "
      f"| {sum(f['size'] for f in filieres if f['cat']=='afternoon')} etudiants")
total_etu = sum(f['size'] for f in filieres)
print(f"  TOTAL : {total_etu} etudiants")
total_cap_all = sum(r['CapaciteTotal'] - BUFFER for r in rooms_data)
print(f"Salles : {len(rooms_data)} | Capacite totale : {total_cap_all} places")
print(f"Creneaux : {num_days} jours x {NUM_SLOT_DAY} = {NUM_SLOTS} creneaux totaux")
print()

# ============================================================
# 4. PHASE 1 – AFFECTATION DES FILIERES AUX CRENEAUX
# ============================================================

print("--- Phase 1 : assignation des creneaux ---")

model1 = cp_model.CpModel()

# Variable de creneau pour chaque filiere
exam_slot_var = {}
f_in_slot = {}

for f in filieres:
    allowed = ([slot_global(d, s) for d in range(num_days) for s in MORNING_IDX]
               if f['cat'] == 'morning'
               else [slot_global(d, s) for d in range(num_days) for s in AFTERNOON_IDX])
    exam_slot_var[f['id']] = model1.NewIntVarFromDomain(
        cp_model.Domain.FromValues(allowed), f"slot_{f['id']}")

    for sl in allowed:
        b = model1.NewBoolVar(f"fis_{f['id']}_{sl}")
        f_in_slot[(f['id'], sl)] = b
        model1.Add(exam_slot_var[f['id']] == sl).OnlyEnforceIf(b)
        model1.Add(exam_slot_var[f['id']] != sl).OnlyEnforceIf(b.Not())

# Contrainte capacite par creneau :
# On limite a MAX_STU_PER_SLOT pour assurer la faisabilite Phase 2
# (eviter de tout mettre dans 1 seul creneau pour l'apres-midi avec 1850 etu)
MAX_STU_PER_SLOT = 1000  # capacite pratique par session
for sl in range(NUM_SLOTS):
    in_slot = [(f, f_in_slot[(f['id'], sl)]) for f in filieres if (f['id'], sl) in f_in_slot]
    if in_slot:
        model1.Add(sum(f['size'] * b for f, b in in_slot) <= MAX_STU_PER_SLOT)

# Objectif : minimiser le nombre de creneaux utilises
slot_used = [model1.NewBoolVar(f"su_{sl}") for sl in range(NUM_SLOTS)]
for sl in range(NUM_SLOTS):
    fids_in = [f_in_slot[(f['id'], sl)] for f in filieres if (f['id'], sl) in f_in_slot]
    if fids_in:
        model1.AddMaxEquality(slot_used[sl], fids_in)
    else:
        model1.Add(slot_used[sl] == 0)

model1.Minimize(sum(slot_used))

solver1 = cp_model.CpSolver()
solver1.parameters.max_time_in_seconds = 30
solver1.parameters.num_search_workers  = 8
solver1.parameters.log_search_progress = False

status1 = solver1.Solve(model1)
if status1 not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    print(f"ERREUR Phase 1 : pas de solution ({solver1.StatusName(status1)})")
    exit(1)

print(f"OK Phase 1 : {'OPTIMALE' if status1==cp_model.OPTIMAL else 'REALISABLE'} | "
      f"{solver1.WallTime():.2f}s")

slot_assignments = {f['id']: solver1.Value(exam_slot_var[f['id']]) for f in filieres}
slot_to_filieres = defaultdict(list)
for f in filieres:
    slot_to_filieres[slot_assignments[f['id']]].append(f)

used_slots = sorted(slot_to_filieres.keys())
print(f"Creneaux utilises : {len(used_slots)} / {NUM_SLOTS}")
for sl in used_slots:
    d, s = sl // NUM_SLOT_DAY, sl % NUM_SLOT_DAY
    fls = slot_to_filieres[sl]
    print(f"  {calendar_data[d]['Jour']:<10} {SLOT_LABELS[s]:<15} | "
          f"{len(fls):>2} filieres | {sum(f['size'] for f in fls):>5} etudiants")
print()

# ============================================================
# 5. PHASE 2 – AFFECTATION DES GROUPES AUX SALLES PAR CRENEAU
# ============================================================

print("--- Phase 2 : affectation des salles par creneau ---")

results = {}   # sl -> list of {salle, cap, filiere, groupe, size}

for sl in used_slots:
    day_idx  = sl // NUM_SLOT_DAY
    slot_loc = sl % NUM_SLOT_DAY
    label    = f"{calendar_data[day_idx]['Jour']} {SLOT_LABELS[slot_loc]}"

    filieres_slot = slot_to_filieres[sl]

    # Construire la liste de groupes pour ce creneau
    groups = []
    for f in filieres_slot:
        for gi, g_size in enumerate(f['groups']):
            groups.append({
                'id'  : f"{f['id']}_g{gi}",
                'name': f"{f['name']} G{gi+1}",
                'type': f['name'],
                'size': g_size,
            })

    total_s = sum(g['size'] for g in groups)

    model2 = cp_model.CpModel()

    # Variables : x[group_id, room_idx] = 1 si groupe dans salle
    x = {}
    for g in groups:
        for r_idx in range(len(rooms_data)):
            x[(g['id'], r_idx)] = model2.NewBoolVar(f"x_{g['id']}_{r_idx}")

    # Variables salle utilisee et occupation
    room_used = [model2.NewBoolVar(f"ru_{r}") for r in range(len(rooms_data))]
    occupancy = [model2.NewIntVar(0, rooms_data[r]['CapaciteTotal'], f"occ_{r}")
                 for r in range(len(rooms_data))]

    # Variables type_present : filiere t presente dans salle r
    unique_types = list(set(g['type'] for g in groups))
    type_present = {}
    for t in unique_types:
        for r_idx in range(len(rooms_data)):
            type_present[(t, r_idx)] = model2.NewBoolVar(f"tp_{t}_{r_idx}")

    # C1 : chaque groupe dans exactement une salle
    for g in groups:
        model2.Add(sum(x[(g['id'], r_idx)] for r_idx in range(len(rooms_data))) == 1)

    # C2 : occupation = somme des effectifs
    for r_idx, r in enumerate(rooms_data):
        cap = r['CapaciteTotal'] - BUFFER
        model2.Add(occupancy[r_idx] == sum(x[(g['id'], r_idx)] * g['size'] for g in groups))
        model2.Add(occupancy[r_idx] <= cap)   # capacite max

    # C3 : lier room_used a l'occupation
    for r_idx in range(len(rooms_data)):
        nb_in_room = sum(x[(g['id'], r_idx)] for g in groups)
        model2.Add(nb_in_room >= 1).OnlyEnforceIf(room_used[r_idx])
        model2.Add(nb_in_room == 0).OnlyEnforceIf(room_used[r_idx].Not())
        # Si la salle est vide, occupation = 0
        model2.Add(occupancy[r_idx] == 0).OnlyEnforceIf(room_used[r_idx].Not())

    # C4 : max 2 filieres differentes par salle
    for r_idx in range(len(rooms_data)):
        for t in unique_types:
            grp_t = [g for g in groups if g['type'] == t]
            if grp_t:
                model2.AddMaxEquality(type_present[(t, r_idx)], [x[(g['id'], r_idx)] for g in grp_t])
            else:
                model2.Add(type_present[(t, r_idx)] == 0)
        model2.Add(sum(type_present[(t, r_idx)] for t in unique_types) <= 2)

    # Objectif multi-criteres :
    #   - minimiser nombre de salles utilisees (poids fort)
    #   - bonus occupation : maximiser la somme des occupations (remplir les salles)
    #   - bonus regroupement batiment : bonus si salles du meme batiment

    W_rooms = 10000
    W_occ   = 1

    # Bonus batiment : pour chaque paire de salles du meme batiment toutes deux utilisees
    building_map = {}
    for r_idx, r in enumerate(rooms_data):
        bat = r['Salle'][0]
        building_map.setdefault(bat, []).append(r_idx)

    bat_bonus = []
    for bat, r_indices in building_map.items():
        for i in range(len(r_indices)):
            for j in range(i+1, len(r_indices)):
                pair_used = model2.NewBoolVar(f"bat_{bat}_{i}_{j}")
                model2.AddBoolAnd([room_used[r_indices[i]], room_used[r_indices[j]]]).OnlyEnforceIf(pair_used)
                model2.AddBoolOr([room_used[r_indices[i]].Not(), room_used[r_indices[j]].Not()]).OnlyEnforceIf(pair_used.Not())
                bat_bonus.append(pair_used)

    W_bat = 5
    total_occ = sum(occupancy[r_idx] for r_idx in range(len(rooms_data)))
    num_used  = sum(room_used)

    model2.Maximize(
        - W_rooms * num_used
        + W_occ   * total_occ
        + W_bat   * sum(bat_bonus)
    )

    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = 90
    solver2.parameters.num_search_workers  = 8
    solver2.parameters.log_search_progress = False

    status2 = solver2.Solve(model2)

    slot_results = []
    if status2 in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for r_idx, r in enumerate(rooms_data):
            if solver2.Value(room_used[r_idx]) == 1:
                assigned = [g for g in groups if solver2.Value(x[(g['id'], r_idx)]) == 1]
                for g in assigned:
                    slot_results.append({
                        'salle'  : r['Salle'],
                        'cap'    : r['CapaciteTotal'] - BUFFER,
                        'filiere': g['type'],
                        'groupe' : g['name'],
                        'size'   : g['size'],
                    })
        status_lbl = 'OK-OPT' if status2 == cp_model.OPTIMAL else 'OK-FEAS'
    else:
        status_lbl = 'ECHEC'

    nb_rooms = len(set(e['salle'] for e in slot_results))
    print(f"  [{status_lbl}] {label:<28} | {len(groups):>3} groupes | "
          f"{total_s:>5} etu | {nb_rooms:>2} salles | {solver2.WallTime():.1f}s")
    results[sl] = slot_results

print()

# ============================================================
# 6. PLANNING COMPLET
# ============================================================

print("=" * 90)
print("                     PLANNING COMPLET DES EXAMENS")
print("=" * 90)

grand_stu  = 0
grand_cap  = 0   # capacite totale des salles utilisees (par salle unique par creneau)
grand_sal  = 0

for day_idx, day_info in enumerate(calendar_data):
    has_slot = any(slot_global(day_idx, s) in results and results[slot_global(day_idx, s)]
                   for s in range(NUM_SLOT_DAY))
    if not has_slot:
        continue

    print(f"\n{'='*90}")
    print(f"  {day_info['Jour'].upper()}  -  {day_info['Date']}")
    print(f"{'='*90}")

    for slot_loc in range(NUM_SLOT_DAY):
        sl = slot_global(day_idx, slot_loc)
        if sl not in results or not results[sl]:
            continue

        entries = results[sl]
        print(f"\n  [Creneau {slot_loc+1}]  {SLOT_LABELS[slot_loc]}")
        print(f"  {'Filiere':<26} {'Groupe':<22} {'Ef':>4}  {'Salle':<6}  {'Cap':>4}  {'Taux':>6}")
        print(f"  {'-'*26} {'-'*22} {'-'*4}  {'-'*6}  {'-'*4}  {'-'*6}")

        salle_totals = defaultdict(int)
        salle_caps   = {}
        for e in sorted(entries, key=lambda e: (e['salle'], e['filiere'], e['groupe'])):
            taux = e['size'] / e['cap'] * 100
            warn = " !" if taux < 30 else ""
            print(f"  {e['filiere']:<26} {e['groupe']:<22} {e['size']:>4}  {e['salle']:<6}  {e['cap']:>4}  {taux:>5.1f}%{warn}")
            salle_totals[e['salle']] += e['size']
            salle_caps[e['salle']]    = e['cap']

        # Stats par salle
        print()
        for salle in sorted(salle_totals):
            cap = salle_caps[salle]
            tot = salle_totals[salle]
            pct = tot / cap * 100
            bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
            print(f"  Salle {salle:<5} [{bar}] {pct:>5.1f}%  ({tot}/{cap})")
            grand_stu += tot
            grand_cap += cap
            grand_sal += 1

# ============================================================
# 7. STATISTIQUES GLOBALES
# ============================================================

print(f"\n{'='*90}")
print("STATISTIQUES GLOBALES")
print(f"{'='*90}")
print(f"  Filieres planifiees       : {len(filieres)}")
print(f"  Etudiants places          : {grand_stu}")
print(f"  Creneaux utilises         : {len(used_slots)} / {NUM_SLOTS}")
print(f"  Utilisations salle x slot : {grand_sal}")
if grand_cap > 0:
    print(f"  Taux global d'occupation  : {grand_stu/grand_cap*100:.1f}%")

print(f"\n  Recapitulatif par creneau :")
print(f"  {'Jour':<10} {'Horaire':<15} {'Filieres':>8} {'Etudiants':>10} {'Salles':>7} {'Taux':>7}")
print(f"  {'-'*10} {'-'*15} {'-'*8} {'-'*10} {'-'*7} {'-'*7}")
for sl in used_slots:
    d, s  = sl // NUM_SLOT_DAY, sl % NUM_SLOT_DAY
    fls   = slot_to_filieres[sl]
    nb_stu_sl = sum(f['size'] for f in fls)
    sal_dict  = {}
    for e in results.get(sl, []):
        sal_dict[e['salle']] = sal_dict.get(e['salle'], 0) + e['size']
    nb_sal = len(sal_dict)
    cap_sl = sum(next(r['CapaciteTotal']-BUFFER for r in rooms_data if r['Salle']==sn) for sn in sal_dict)
    taux_sl = (sum(sal_dict.values()) / cap_sl * 100) if cap_sl else 0
    placed_sl = sum(sal_dict.values())
    print(f"  {calendar_data[d]['Jour']:<10} {SLOT_LABELS[s]:<15} {len(fls):>8} {placed_sl:>10} {nb_sal:>7} {taux_sl:>6.1f}%")

print(f"{'='*90}")
