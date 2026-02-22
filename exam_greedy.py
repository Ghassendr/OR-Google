import sys, json, math, random, time
from collections import defaultdict
from ortools.sat.python import cp_model

# ============================================================
# 1. CHARGEMENT
# ============================================================

with open('class.json',  'r', encoding='utf-8') as f:
    rooms_data = json.load(f)

with open('filier.json', 'r', encoding='utf-8') as f:
    try:
        filieres_raw = json.load(f)
        if not isinstance(filieres_raw, dict) or 'annees' not in filieres_raw:
            # Handle list format or malformed data
            if isinstance(filieres_raw, list) and len(filieres_raw) > 0:
                 filieres_raw = {"annees": {"custom_import": {"filieres": {f.get('Filiere', f.get('filiere', '')): f.get('Effectif', f.get('effectif', 0)) for f in filieres_raw}}}}
            else:
                filieres_raw = {"annees": {}}
    except:
        filieres_raw = {"annees": {}}

BUFFER = 4

# ============================================================
# 2. CONSTRUCTION DES FILIERES
# ============================================================

morning_fils = []
afternoon_fils = []

annees = filieres_raw.get('annees', {})
year_labels = {'1ere_annee': 'L1', '2eme_annee': 'L2', '3eme_annee': 'L3', 'master': 'M'}

for annee_key, annee_val in annees.items():
    sub = annee_val.get('programmes', {}) if annee_key == 'master' else annee_val.get('filieres', {})
    label = year_labels.get(annee_key, annee_key)
    
    for nom, effectif in sub.items():
        if effectif == 0: continue
        
        filiere = {
            'name': f"{label} {nom}",
            'size': effectif,
            'remaining': effectif,
            'groups': [] # For output consistency
        }
        
        # Categorisation blocs
        if annee_key in ['master', '1ere_annee'] or 'Ingenieur' in nom or 'Cycle_Preparatoire' in nom or 'custom_import' in annee_key:
            morning_fils.append(filiere)
        else:
            afternoon_fils.append(filiere)

# Handle empty state
EMPTY_MODE = (len(morning_fils) == 0 and len(afternoon_fils) == 0)

# ============================================================
# 3. ALGORITHME GLOUTON (GREEDY PAIRING)
# ============================================================

MIN_OCCUPANCY = 0.70 # Taux de remplissage minimum souhaité

# ============================================================
# 3. ALGORITHME GLOUTON (GREEDY PAIRING)
# ============================================================

def greedy_solve(bloc_name, filieres, rooms_data):
    """
    Remplace l'algorithme glouton par un modèle CP-SAT à variables entières.
    Beaucoup plus précis pour l'équilibre et le remplissage à 70%.
    """
    model = cp_model.CpModel()
    
    nf = len(filieres)
    nr = len(rooms_data)
    
    # Variables : x[fi, ri] = nombre d'étudiants de la filière fi dans la salle ri
    x = {}
    for fi in range(nf):
        for ri in range(nr):
            x[(fi, ri)] = model.NewIntVar(0, filieres[fi]['size'], f"x_{fi}_{ri}")
            
    # room_used[ri] = 1 si la salle ri est utilisée
    room_used = [model.NewBoolVar(f"ru_{ri}") for ri in range(nr)]
    
    # fil_present[fi, ri] = 1 si la filière fi est dans la salle ri
    fil_present = {}
    for fi in range(nf):
        for ri in range(nr):
            fil_present[(fi, ri)] = model.NewBoolVar(f"fp_{fi}_{ri}")
            # Liaison : x > 0 <=> fil_present = 1
            model.Add(x[(fi, ri)] > 0).OnlyEnforceIf(fil_present[(fi, ri)])
            model.Add(x[(fi, ri)] == 0).OnlyEnforceIf(fil_present[(fi, ri)].Not())

    # Contraintes transversales
    for fi in range(nf):
        # Tous les étudiants placés
        model.Add(sum(x[(fi, ri)] for ri in range(nr)) == filieres[fi]['size'])
        
    for ri in range(nr):
        cap_total = rooms_data[ri]['CapaciteTotal']
        cap_eff = cap_total - BUFFER
        
        # Somme dans la salle
        occ_ri = sum(x[(fi, ri)] for fi in range(nf))
        
        # Liaison usage
        model.Add(occ_ri > 0).OnlyEnforceIf(room_used[ri])
        model.Add(occ_ri == 0).OnlyEnforceIf(room_used[ri].Not())
        
        # Capacité max
        model.Add(occ_ri <= cap_eff)
        
        # RENTABILITE : Min 70% si utilisé
        model.Add(occ_ri >= int(cap_total * MIN_OCCUPANCY)).OnlyEnforceIf(room_used[ri])
        
        # MIXITE OBLIGATOIRE : Exactement 2 filières
        model.Add(sum(fil_present[(fi, ri)] for fi in range(nf)) == 2).OnlyEnforceIf(room_used[ri])
        
        # EQUILIBRE : |f1 - f2| <= 4
        # Pour une salle partagée par fi et fj, on veut |x[fi,ri] - x[fj,ri]| <= 4
        # On peut simplifier en disant 2 * x[fi,ri] - occ_ri <= 4
        for fi in range(nf):
            model.Add(2 * x[(fi, ri)] - occ_ri <= 4).OnlyEnforceIf(fil_present[(fi, ri)])
            model.Add(occ_ri - 2 * x[(fi, ri)] <= 4).OnlyEnforceIf(fil_present[(fi, ri)])

    # Objectif : Minimiser le nombre de salles
    model.Minimize(sum(room_used))
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0 # Rapide
    solver.parameters.num_search_workers  = 16
    status = solver.Solve(model)
    
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
                            'eff_cap': rooms_data[ri]['CapaciteTotal'] - BUFFER,
                            'filiere': filieres[fi]['name'],
                            'size': val,
                            'total_in_room': tot
                        })
    return results

    return results

# ============================================================
# 4. RESOLUTION ET AFFICHAGE
# ============================================================

def solve_with_timer(name, filieres, rooms):
    start = time.time()
    res = greedy_solve(name, filieres, rooms)
    duration = time.time() - start
    return res, duration

res_morning, dur_morning = solve_with_timer("MATIN", morning_fils, rooms_data) if not EMPTY_MODE else ([], 0)
res_afternoon, dur_afternoon = solve_with_timer("APRES-MIDI", afternoon_fils, rooms_data) if not EMPTY_MODE else ([], 0)

def get_stats(results):
    if not results: return 0, 0
    salles = len(set(r['salle'] for r in results))
    students = sum(r['size'] for r in results)
    return salles, students

def display_bloc(bloc_name, results, duration):
    if not results:
        print(f"  Aucun résultat pour {bloc_name}.")
        return

    per_room = defaultdict(list)
    for r in results:
        per_room[r['salle']].append(r)

    salles_sorted = sorted(per_room.keys(), key=lambda s: (s[0], s))
    nb_rooms, total_stu = get_stats(results)
    
    print("=" * 75)
    print(f"  {bloc_name} | Durée: {duration:.4f}s")
    print("=" * 75)
    print(f"\n  {'Salle':<6}  {'Cap':>4}  {'Total':>8}  {'Taux':>5}  {'Filieres / Groupes'}")
    print(f"  {'-'*6}  {'-'*4}  {'-'*8}  {'-'*5}  {'-'*50}")

    total_cap = 0
    prev_bat = None
    
    for s_name in salles_sorted:
        ents = per_room[s_name]
        real_cap = ents[0]['real_cap']
        tot = ents[0]['total_in_room']
        pct = (tot / real_cap * 100) if real_cap > 0 else 0
        total_cap += real_cap
        
        bat = s_name[0]
        if bat != prev_bat:
            if prev_bat is not None: print()
            prev_bat = bat

        bar = '#' * int(pct/5) + '.' * (20 - int(pct/5))
        print(f"  {s_name:<6}  {real_cap:>4}  {tot:>8}  {pct:>4.0f}%  [{bar}]")
        for e in ents:
            print(f"         {'':>14}  {e['filiere']:<22} {e['size']:>4} etu")

    print(f"\n  TOTAL {bloc_name}:")
    print(f"  - Salles utilisées   : {nb_rooms}")
    print(f"  - Étudiants placés   : {total_stu}")
    print(f"  - Temps d'exécution : {duration:.4f}s")
    print("=" * 75 + "\n")

display_bloc("BLOC MATIN", res_morning, dur_morning)
display_bloc("BLOC APRES-MIDI", res_afternoon, dur_afternoon)

def save_results_to_json(morning_res, afternoon_res):
    # Prepare data structure for the frontend
    s_matin = []
    for s_name in sorted(set(r['salle'] for r in morning_res), key=lambda s: (s[0], s)):
        ents = [r for r in morning_res if r['salle'] == s_name]
        s_matin.append({
            'id': s_name,
            'cap': ents[0]['real_cap'],
            'fill': int(ents[0]['total_in_room'] / ents[0]['real_cap'] * 100) if ents[0]['real_cap'] > 0 else 0,
            'groupes': [{'n': r['filiere'].split()[0], 'f': ' '.join(r['filiere'].split()[1:]), 'e': r['size']} for r in ents]
        })

    s_apmidi = []
    for s_name in sorted(set(r['salle'] for r in afternoon_res), key=lambda s: (s[0], s)):
        ents = [r for r in afternoon_res if r['salle'] == s_name]
        s_apmidi.append({
            'id': s_name,
            'cap': ents[0]['real_cap'],
            'fill': int(ents[0]['total_in_room'] / ents[0]['real_cap'] * 100) if ents[0]['real_cap'] > 0 else 0,
            'groupes': [{'n': r['filiere'].split()[0], 'f': ' '.join(r['filiere'].split()[1:]), 'e': r['size']} for r in ents]
        })

    data = {
        'matin': s_matin,
        'apmidi': s_apmidi,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open('placement.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("  [JSON] Résultats sauvegardés dans : placement.json")

# ============================================================
# 6. RECAPITULATIF ET EXECUTION FINALE
# ============================================================

sm_rooms, sm_stu = get_stats(res_morning)
sa_rooms, sa_stu = get_stats(res_afternoon)
print("=" * 75)
print("  RECAPITULATIF GLOBAL (CP-SAT/GREEDY MIX)")
print("=" * 75)
print(f"  {'Bloc':<20} {'Salles':>7} {'Étudiants':>10} {'Temps':>10}")
print(f"  {'-'*20} {'-'*7} {'-'*10} {'-'*10}")
print(f"  {'Matin':<20} {sm_rooms:>7} {sm_stu:>10} {dur_morning:>9.4f}s")
print(f"  {'Après-midi':<20} {sa_rooms:>7} {sa_stu:>10} {dur_afternoon:>9.4f}s")
print(f"  {'-'*20} {'-'*7} {'-'*10} {'-'*10}")
print(f"  {'TOTAL':<20} {sm_rooms+sa_rooms:>7} {sm_stu+sa_stu:>10} {dur_morning+dur_afternoon:>9.4f}s")
print("=" * 75)
save_results_to_json(res_morning, res_afternoon)
