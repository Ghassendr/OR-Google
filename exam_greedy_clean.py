import sys, json, math, random, time
from collections import defaultdict
from ortools.sat.python import cp_model

# ---------------- LOAD DATA ----------------
with open('class.json',  'r', encoding='utf-8') as f:
    rooms_data = json.load(f)

with open('filier.json', 'r', encoding='utf-8') as f:
    try:
        filieres_raw = json.load(f)
        if not isinstance(filieres_raw, dict) or 'annees' not in filieres_raw:
            if isinstance(filieres_raw, list) and len(filieres_raw) > 0:
                 filieres_raw = {"annees": {"custom_import": {"filieres": {
                     f.get('Filiere', f.get('filiere', '')): f.get('Effectif', f.get('effectif', 0))
                     for f in filieres_raw}}}}
            else:
                filieres_raw = {"annees": {}}
    except:
        filieres_raw = {"annees": {}}

BUFFER = 4
MIN_OCCUPANCY = 0.70

morning_fils = []
afternoon_fils = []

annees = filieres_raw.get('annees', {})
year_labels = {'1ere_annee': 'L1', '2eme_annee': 'L2', '3eme_annee': 'L3', 'master': 'M'}

# ---------------- PREP DATA ----------------
for annee_key, annee_val in annees.items():
    sub = annee_val.get('programmes', {}) if annee_key == 'master' else annee_val.get('filieres', {})
    label = year_labels.get(annee_key, annee_key)

    for nom, effectif in sub.items():
        if effectif == 0:
            continue

        filiere = {
            'name': f"{label} {nom}",
            'size': effectif
        }

        if annee_key in ['master', '1ere_annee'] or 'Ingenieur' in nom or 'Cycle_Preparatoire' in nom or 'custom_import' in annee_key:
            morning_fils.append(filiere)
        else:
            afternoon_fils.append(filiere)

EMPTY_MODE = (len(morning_fils) == 0 and len(afternoon_fils) == 0)

# ---------------- SOLVER ----------------
def greedy_solve(bloc_name, filieres, rooms_data):

    model = cp_model.CpModel()
    nf = len(filieres)
    nr = len(rooms_data)

    BLOCS = ['M', 'J', 'I', 'K']

    # VARIABLES
    x = {}
    fil_present = {}
    bloc = {}

    for fi in range(nf):
        bloc[fi] = model.NewIntVar(0, len(BLOCS)-1, f"bloc_{fi}")

        for ri in range(nr):
            x[(fi, ri)] = model.NewIntVar(0, filieres[fi]['size'], f"x_{fi}_{ri}")

            fil_present[(fi, ri)] = model.NewBoolVar(f"fp_{fi}_{ri}")
            model.Add(x[(fi, ri)] > 0).OnlyEnforceIf(fil_present[(fi, ri)])
            model.Add(x[(fi, ri)] == 0).OnlyEnforceIf(fil_present[(fi, ri)].Not())

    room_used = [model.NewBoolVar(f"ru_{ri}") for ri in range(nr)]

    # ---------------- HARD CONSTRAINT: SAME CLASS SAME BLOC ----------------
    groups = defaultdict(list)

    for fi, f in enumerate(filieres):
        parts = f['name'].split()
        if parts[-1].isdigit():
            base = ' '.join(parts[:-1])
        else:
            base = f['name']
        groups[base].append(fi)

    for base, fis in groups.items():
        for i in range(len(fis) - 1):
            model.Add(bloc[fis[i]] == bloc[fis[i+1]])

    # ---------------- ASSIGNMENT ----------------
    for fi in range(nf):
        model.Add(sum(x[(fi, ri)] for ri in range(nr)) == filieres[fi]['size'])

    for ri in range(nr):
        cap_total = rooms_data[ri]['CapaciteTotal']
        cap_eff = cap_total - BUFFER

        occ_ri = sum(x[(fi, ri)] for fi in range(nf))

        model.Add(occ_ri > 0).OnlyEnforceIf(room_used[ri])
        model.Add(occ_ri == 0).OnlyEnforceIf(room_used[ri].Not())

        model.Add(occ_ri <= cap_eff)
        model.Add(occ_ri >= int(cap_total * MIN_OCCUPANCY)).OnlyEnforceIf(room_used[ri])

        model.Add(sum(fil_present[(fi, ri)] for fi in range(nf)) == 2).OnlyEnforceIf(room_used[ri])

        for fi in range(nf):
            model.Add(2 * x[(fi, ri)] - occ_ri <= 4).OnlyEnforceIf(fil_present[(fi, ri)])
            model.Add(occ_ri - 2 * x[(fi, ri)] <= 4).OnlyEnforceIf(fil_present[(fi, ri)])

    # ---------------- LINK BLOC TO ROOM ----------------
    for fi in range(nf):
        for ri in range(nr):
            room_bloc_letter = rooms_data[ri]['Salle'][0]
            room_bloc = BLOCS.index(room_bloc_letter)

            model.Add(bloc[fi] == room_bloc).OnlyEnforceIf(fil_present[(fi, ri)])

    # OBJECTIVE
    model.Minimize(sum(room_used))

    # SOLVE
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    solver.parameters.num_search_workers = 16

    status = solver.Solve(model)

    # ---------------- RESULTS ----------------
    results = []

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for ri in range(nr):
            if solver.Value(room_used[ri]):
                tot = sum(solver.Value(x[(fi, ri)]) for fi in range(nf))

                for fi in range(nf):
                    val = solver.Value(x[(fi, ri)])
                    if val > 0:
                        results.append({
                            'salle': rooms_data[ri]['Salle'],
                            'bat': rooms_data[ri]['Salle'][0],
                            'real_cap': rooms_data[ri]['CapaciteTotal'],
                            'filiere': filieres[fi]['name'],
                            'size': val,
                            'total_in_room': tot
                        })

    return results

# ---------------- RUN ----------------
def solve_with_timer(name, filieres, rooms):
    start = time.time()
    res = greedy_solve(name, filieres, rooms)
    duration = time.time() - start
    return res, duration

res_morning, dur_morning = solve_with_timer("MATIN", morning_fils, rooms_data) if not EMPTY_MODE else ([], 0)
res_afternoon, dur_afternoon = solve_with_timer("APRES-MIDI", afternoon_fils, rooms_data) if not EMPTY_MODE else ([], 0)

# ---------------- DISPLAY ----------------
def display_bloc(bloc_name, results, duration):
    if not results:
        print(f"Aucun résultat pour {bloc_name}")
        return

    per_room = defaultdict(list)
    for r in results:
        per_room[r['salle']].append(r)

    print(f"\n=== {bloc_name} | {duration:.2f}s ===")

    for salle, ents in per_room.items():
        print(f"\n{salle} ({ents[0]['real_cap']}) total={ents[0]['total_in_room']}")
        for e in ents:
            print(f"  - {e['filiere']} : {e['size']}")

display_bloc("MATIN", res_morning, dur_morning)
display_bloc("APRES-MIDI", res_afternoon, dur_afternoon)