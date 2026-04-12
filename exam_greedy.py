import sys, json, math, random, time, os
from collections import defaultdict
from ortools.sat.python import cp_model

try:
    import mysql.connector
except ImportError:
    mysql = None

# Database Config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'gestion_examens_s1')
}

filieres_raw = {"annees": {}}

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    # Load Rooms
    cursor.execute("SELECT name AS Salle, capacity AS CapaciteTotal FROM salle ORDER BY name")
    rooms_data = cursor.fetchall()
    
    # Load Filieres from DB and transform to JSON-like structure
    cursor.execute("SELECT abreviation_filaire, annee, type_filaire, effectif FROM filaire WHERE effectif > 0")
    db_fils = cursor.fetchall()
    
    if db_fils:
        for f in db_fils:
            # Map DB enums to JSON keys
            annee_raw = f['annee']
            type_raw = f['type_filaire']
            
            annee_key = '1ere_annee'
            if annee_raw == '2EME': annee_key = '2eme_annee'
            elif annee_raw == '3EME':
                if type_raw in ['MASTER_PRO', 'MASTER_RECHERCHE']: annee_key = 'master'
                else: annee_key = '3eme_annee'
            
            if annee_key not in filieres_raw["annees"]:
                filieres_raw["annees"][annee_key] = {"filieres": {}, "programmes": {}}
            
            sub_key = "programmes" if annee_key == "master" else "filieres"
            filieres_raw["annees"][annee_key][sub_key][f['abreviation_filaire']] = f['effectif']
            
        print(f"  [DB] {len(rooms_data)} salles et {len(db_fils)} filières chargées.")
    else:
        raise Exception("No filieres found in DB")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"  [DB Info] Chargement depuis filier.json (Repli): {e}")
    if os.path.exists('filier.json'):
        with open('filier.json', 'r', encoding='utf-8') as f:
            try:
                raw = json.load(f)
                if isinstance(raw, list):
                    filieres_raw = {"annees": {"custom_import": {"filieres": {x.get('Filiere',''): x.get('Effectif',0) for x in raw}}}}
                else:
                    filieres_raw = raw
            except: pass

BUFFER = 4

# ============================================================
# 2. CONSTRUCTION DES FILIERES
# ============================================================

morning_fils = []
afternoon_fils = []

annees = filieres_raw.get('annees', {})
year_labels = {'1ere_annee': 'L1', '2eme_annee': 'L2', '3eme_annee': 'L3', 'master': 'M'}

for annee_key, annee_val in annees.items():
    if annee_key == 'master': continue
    
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
# 3. CONFIGURATION & PARAMETRES DYNAMIQUES
# ============================================================

# Valeurs par défaut
MIN_OCCUPANCY = 0.70
BALANCE_SLACK = 5
BUFFER = 4
EXACT_2_GROUPS = True
BUILDING_BLOC = True
OPTIMIZE_ROOMS = True

config_path = os.path.join('data', 'solver_config.json')
if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            MIN_OCCUPANCY = cfg.get('min_occ', MIN_OCCUPANCY)
            BALANCE_SLACK = cfg.get('balance_slack', BALANCE_SLACK)
            BUFFER = cfg.get('buffer', BUFFER)
            EXACT_2_GROUPS = cfg.get('exact_2', EXACT_2_GROUPS)
            BUILDING_BLOC = cfg.get('building_bloc', BUILDING_BLOC)
            OPTIMIZE_ROOMS = cfg.get('optimize_rooms', OPTIMIZE_ROOMS)
            print(f"  [Config] Paramètres chargés: Occ={MIN_OCCUPANCY}, Buffer={BUFFER}")
    except Exception as e:
        print(f"  [Config Error] Erreur chargement config, utilisation défauts: {e}")

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

    # NOUVEAU : Regroupement par bâtiment
    # bats = set de tous les premiers caractères des noms de salles (ex: 'K', 'M', 'I', 'J')
    bats = sorted(list(set(rooms_data[ri]['Salle'][0] for ri in range(nr))))
    bat_to_ri = {b: [ri for ri in range(nr) if rooms_data[ri]['Salle'][0] == b] for b in bats}
    
    # fil_in_bat[fi, b] = 1 si la filière fi est présente dans le bâtiment b
    fil_in_bat = {}
    for fi in range(nf):
        for b in bats:
            fil_in_bat[(fi, b)] = model.NewBoolVar(f"fib_{fi}_{b}")
            # Si un étudiant de fi est dans une salle ri du bâtiment b, alors fil_in_bat = 1
            # On utilise une contrainte de maximum ou OR
            rooms_in_bat = bat_to_ri[b]
            model.AddMaxEquality(fil_in_bat[(fi, b)], [fil_present[(fi, ri)] for ri in rooms_in_bat])

    # REGROUPEMENT (SOFT CONSTRAINT FORTE) : On minimise le nombre de bâtiments par filière
    # L'objectif est de tendre vers 1 bâtiment par filière, mais sans bloquer s'il faut splitter.
    obj_rooms = sum(room_used)
    obj_bats = sum(fil_in_bat.values())
    
    # On donne une priorité extrêmement élevée au regroupement par bâtiment
    # tout en gardant l'utilisation des salles comme base.
    model.Minimize(100 * obj_rooms + 5000 * obj_bats)
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
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

    # Save to Database `salle_filieres`
    if mysql:
        try:
            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST', '127.0.0.1'),
                port=int(os.getenv('DB_PORT', '3306')),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', ''),
                database=os.getenv('DB_NAME', 'gestion_examens_s1'),
                charset='utf8mb4'
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id_filaire, nom_filaire, abreviation_filaire FROM filaire")
            filieres_db = cursor.fetchall()

            cursor.execute("TRUNCATE TABLE salle_filieres")

            def find_filiere_id(name_with_label):
                parts = name_with_label.split(' ', 1)
                f_name = parts[1] if len(parts) > 1 else name_with_label
                
                f_name_lower = f_name.strip().lower()
                f_clean = f_name_lower.replace('l_', '').replace('mr_', '').replace('mp_', '').replace('_', ' ').strip()
                
                # Try exact match with multiple variations
                for db_f in filieres_db:
                    db_nom = db_f['nom_filaire'].strip().lower()
                    db_abrev = (db_f['abreviation_filaire'] or '').strip().lower()
                    
                    if f_name_lower == db_nom or f_clean == db_nom:
                        return db_f['id_filaire']
                    if f_name_lower == db_abrev or f_clean == db_abrev:
                        return db_f['id_filaire']
                        
                    if db_abrev and (f_clean == db_abrev.replace('-', ' ') or f_clean == db_abrev.replace('-', '')):
                        return db_f['id_filaire']
                        
                    # Specific fixes for common prefixes "Licence ", "Master "
                    if db_abrev and db_abrev in f_name_lower:
                        return db_f['id_filaire']
                
                # Try partial match
                for db_f in filieres_db:
                    db_nom = db_f['nom_filaire'].strip().lower()
                    if f_clean in db_nom or db_nom in f_clean:
                        return db_f['id_filaire']
                
                # Ultimate fallback for entries missing in DB
                fallbacks = {
                    'energ': 3,      # Map to Licence Eng
                    'pai': 35,       # Map to Master MERE
                    'spi 2': 38,     # Map to Master MR-SPI
                    'spi 1': 38
                }
                for key, val in fallbacks.items():
                    if key in f_clean:
                        return val
                        
                return None

            insert_query = "INSERT INTO salle_filieres (salle_name, type_session, id_filiere1, id_filiere2) VALUES (%s, %s, %s, %s)"
            
            def process_db(data_list, session_name):
                per_room = defaultdict(list)
                for r in data_list:
                    per_room[r['salle']].append(r)
                
                for s_name, records in per_room.items():
                    f_list = list(set([r['filiere'] for r in records]))
                    id1 = find_filiere_id(f_list[0]) if len(f_list) > 0 else None
                    id2 = find_filiere_id(f_list[1]) if len(f_list) > 1 else None
                    cursor.execute(insert_query, (s_name, session_name, id1, id2))
            
            process_db(morning_res, 'matin')
            process_db(afternoon_res, 'apmidi')
            
            conn.commit()
            cursor.close()
            conn.close()
            print("  [DB] Résultats sauvegardés dans : salle_filieres")
        except Exception as e:
            print("  [DB Error] Impossible de sauvegarder dans la base :", str(e))

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
