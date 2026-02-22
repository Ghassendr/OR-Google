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
    if not results: return 0, 0, 0
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

# ============================================================
# 5. GENERATION RAPPORT HTML (AVANCÉ)
# ============================================================

def generate_html_report(morning_res, afternoon_res, morning_dur, afternoon_dur):
    # Pre-calculate data for the template
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

    total_stu = sum(r['size'] for r in morning_res + afternoon_res)
    total_rooms_count = len(set(r['salle'] for r in morning_res + afternoon_res))
    total_cap_all = sum(r['real_cap'] for r in morning_res + afternoon_res)
    global_pct = (total_stu / total_cap_all * 100) if total_cap_all > 0 else 0
    
    html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1.0" />
    <title>Dashboard Examens 2026</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tesseract.js/4.1.1/tesseract.min.js"></script>
    <style>
        :root {{
            --bg: #F5F3EE;
            --surface: #FFFFFF;
            --surface2: #F9F7F3;
            --border: #E2DDD5;
            --border2: #CFC9BE;
            --navy: #1B3A6B;
            --navy2: #254D8F;
            --amber: #C67C0D;
            --amber-lt: #FDF3E0;
            --green: #2D6A4F;
            --green-lt: #E8F5EE;
            --red: #B02A37;
            --red-lt: #FDECEA;
            --text: #1A1714;
            --text2: #4A453E;
            --text3: #8C8078;
            --shadow: 0 1px 4px rgba(0, 0, 0, .07), 0 4px 16px rgba(0, 0, 0, .05);
            --shadow2: 0 2px 8px rgba(0, 0, 0, .10), 0 8px 32px rgba(0, 0, 0, .07);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0 }}
        html {{ scroll-behavior: smooth }}
        body {{ background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; font-size: 14px; line-height: 1.5 }}
        .wrapper {{ max-width: 1400px; margin: 0 auto; padding: 28px 24px }}
        .header {{ background: var(--navy); border-radius: 16px; padding: 28px 36px; margin-bottom: 22px; display: flex; flex-wrap: wrap; gap: 20px; align-items: center; justify-content: space-between; box-shadow: var(--shadow2); position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; inset: 0; background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E") repeat; }}
        .header-title {{ position: relative }}
        .header-eyebrow {{ font-size: 10px; letter-spacing: 3px; color: #92AACF; text-transform: uppercase; font-weight: 600; margin-bottom: 6px }}
        .header-h1 {{ font-family: 'DM Serif Display', serif; font-size: 28px; color: #fff; line-height: 1.1; margin-bottom: 4px }}
        .header-sub {{ font-size: 12px; color: #6B8BBF }}
        .stats-row {{ display: flex; gap: 12px; flex-wrap: wrap; position: relative }}
        .stat-box {{ background: rgba(255, 255, 255, .09); border: 1px solid rgba(255, 255, 255, .12); border-radius: 10px; padding: 12px 18px; min-width: 110px }}
        .stat-label {{ font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: #92AACF; font-weight: 600; margin-bottom: 4px }}
        .stat-val {{ font-family: 'DM Serif Display', serif; font-size: 24px; color: #fff }}
        .stat-val.amber {{ color: #F5B942 }}
        .stat-val.green {{ color: #5DDBA4 }}
        .stat-val.blue {{ color: #7EB3FF }}
        .controls {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 20px; margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; box-shadow: var(--shadow); }}
        .tab-group {{ display: flex; gap: 4px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 4px }}
        .tab {{ padding: 7px 18px; border-radius: 6px; border: none; cursor: pointer; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 600; transition: all .2s; color: var(--text3); background: transparent }}
        .tab.active {{ background: var(--navy); color: #fff; box-shadow: 0 2px 8px rgba(27, 58, 107, .3) }}
        .tab:hover:not(.active) {{ background: var(--border); color: var(--text2) }}
        .divider {{ width: 1px; height: 28px; background: var(--border) }}
        .search-wrap {{ position: relative; margin-left: auto }}
        .search-wrap svg {{ position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text3) }}
        .search {{ border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px 8px 34px; font-family: 'DM Sans', sans-serif; font-size: 13px; color: var(--text); background: var(--surface2); outline: none; width: 220px; transition: border .2s }}
        .search:focus {{ border-color: var(--navy2); background: #fff }}
        .import-bar {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 14px; align-items: center; box-shadow: var(--shadow); }}
        .import-title {{ font-weight: 600; color: var(--text2); font-size: 13px; letter-spacing: .3px; margin-right: 4px }}
        .btn {{ display: inline-flex; align-items: center; gap: 7px; padding: 9px 18px; border-radius: 8px; border: none; cursor: pointer; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 600; transition: all .18s; white-space: nowrap }}
        .btn-photo {{ background: var(--amber-lt); color: var(--amber); border: 1.5px solid #F0C97020 }}
        .btn-excel {{ background: var(--green-lt); color: var(--green); border: 1.5px solid #2D6A4F20 }}
        .btn-lancer {{ background: var(--navy); color: #fff; margin-left: auto; }}
        .btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}
        input[type=file] {{ display: none }}
        .import-status {{ font-size: 12px; color: var(--text3); font-style: italic }}
        .legend {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px 18px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 16px; align-items: center; box-shadow: var(--shadow); }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text2) }}
        .legend-dot {{ width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0 }}
        .legend-sep {{ margin-left: auto; display: flex; gap: 14px }}
        .fill-legend {{ display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text3) }}
        .fill-dot {{ width: 8px; height: 8px; border-radius: 50% }}
        .section-info {{ font-size: 11px; color: var(--text3); margin-bottom: 12px; font-family: 'DM Sans', sans-serif; letter-spacing: .3px }}
        .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); transition: all .2s; cursor: default; }}
        .card:hover {{ box-shadow: var(--shadow2); transform: translateY(-2px); border-color: var(--border2) }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px }}
        .card-id {{ font-family: 'DM Serif Display', serif; font-size: 17px; color: var(--navy); letter-spacing: .5px }}
        .card-cap {{ font-size: 11px; color: var(--text3) }}
        .card-cap span {{ color: var(--text2); font-weight: 600 }}
        .fill-bar-bg {{ height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-bottom: 8px }}
        .fill-bar-fg {{ height: 100%; border-radius: 3px; transition: width .5s ease }}
        .fill-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px }}
        .fill-label {{ font-size: 11px; color: var(--text3) }}
        .fill-pct {{ font-size: 13px; font-weight: 700; font-family: 'DM Sans', sans-serif }}
        .groups {{ display: flex; flex-direction: column; gap: 6px }}
        .group-row {{ display: flex; justify-content: space-between; align-items: center; background: var(--surface2); border-radius: 7px; padding: 6px 10px; border-left: 3px solid transparent; }}
        .group-name {{ font-size: 12px; color: var(--text2) }}
        .niveau-badge {{ font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; margin-right: 5px }}
        .group-etu {{ font-size: 12px; font-weight: 700; color: var(--text); white-space: nowrap }}
        .group-etu span {{ font-weight: 400; color: var(--text3) }}
        .niv-L1 {{ background: #FFF0CC; color: #A0640A }}
        .grp-L1 {{ border-left-color: #F5B942 }}
        .niv-L2 {{ background: #D6F5E5; color: #1A6040 }}
        .grp-L2 {{ border-left-color: #3DAD7A }}
        .niv-L3 {{ background: #D6E8FF; color: #1A3F80 }}
        .grp-L3 {{ border-left-color: #4F86D6 }}
        .niv-M {{ background: #EDE0FF; color: #5A1F99 }}
        .grp-M {{ border-left-color: #9B5DE5 }}
        .fill-low {{ background: #3DAD7A }}
        .fill-mid {{ background: #F5A623 }}
        .fill-hi {{ background: #D94040 }}
        .fil-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px }}
        .fil-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); transition: all .2s; }}
        .fil-card:hover {{ box-shadow: var(--shadow2); transform: translateY(-2px) }}
        .fil-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px }}
        .fil-name {{ font-weight: 600; font-size: 14px; color: var(--text) }}
        .fil-total {{ font-family: 'DM Serif Display', serif; font-size: 22px; color: var(--navy) }}
        .fil-chips {{ display: flex; flex-wrap: wrap; gap: 5px; border-top: 1px solid var(--border); padding-top: 10px }}
        .chip {{ background: var(--surface2); border: 1px solid var(--border); border-radius: 5px; padding: 3px 9px; font-size: 11px; color: var(--text2) }}
        .chip strong {{ color: var(--text); font-weight: 700 }}
        .import-section {{ margin-top: 28px }}
        .import-section-title {{ font-family: 'DM Serif Display', serif; font-size: 20px; color: var(--navy); margin-bottom: 14px; display: flex; align-items: center; gap: 10px }}
        .json-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }}
        .json-header {{ background: var(--surface2); border-bottom: 1px solid var(--border); padding: 10px 18px; display: flex; justify-content: space-between; align-items: center; }}
        .json-header-title {{ font-weight: 600; font-size: 13px; color: var(--text2) }}
        .badge-count {{ background: var(--navy); color: #fff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 20px }}
        .btn-save {{ padding: 7px 18px; border-radius: 8px; background: var(--green); color: #fff; border: none; cursor: pointer; font-family: 'DM Sans', sans-serif; font-weight: 600; transition: all .2s; }}
        .table-wrap {{ overflow-x: auto; max-height: 420px; overflow-y: auto }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px }}
        thead tr {{ background: var(--surface2); position: sticky; top: 0; z-index: 2 }}
        th {{ padding: 10px 16px; text-align: left; font-weight: 600; font-size: 11px; letter-spacing: .8px; text-transform: uppercase; color: var(--text3); border-bottom: 2px solid var(--border); }}
        td {{ padding: 10px 16px; border-bottom: 1px solid var(--border); color: var(--text2) }}
        tr:hover td {{ background: var(--surface2) }}
        .td-json {{ font-family: 'Courier New', monospace; font-size: 11px; color: var(--text3); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }}
        .preview-img {{ max-width: 200px; max-height: 120px; border-radius: 8px; border: 1px solid var(--border); object-fit: cover }}
        .progress-bar {{ height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; width: 200px }}
        .progress-fg {{ height: 100%; background: var(--amber); border-radius: 2px; transition: width .3s }}
        footer {{ margin-top: 36px; padding: 14px 0; border-top: 1px solid var(--border); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 11px; color: var(--text3) }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px) }} to {{ opacity: 1; transform: translateY(0) }} }}
        .fade-in {{ animation: fadeIn .3s ease forwards }}
        .empty-state {{ text-align: center; padding: 48px 24px; color: var(--text3) }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <div class="header-title">
                <div class="header-eyebrow">◈ Système GREEDY Optimisé</div>
                <h1 class="header-h1">Dashboard Examens 2026</h1>
                <p class="header-sub">Session d'Examen · Rapport de Placement · Généré le {time.strftime("%d/%m/%Y %H:%M")}</p>
            </div>
            <div class="stats-row">
                <div class="stat-box"><div class="stat-label">Étudiants</div><div class="stat-val amber">{total_stu}</div></div>
                <div class="stat-box"><div class="stat-label">Salles Total</div><div class="stat-val blue">{total_rooms_count}</div></div>
                <div class="stat-box"><div class="stat-label">Ce Bloc</div><div class="stat-val" id="stat-bloc">—</div></div>
                <div class="stat-box"><div class="stat-label">Taux Moy.</div><div class="stat-val green" id="stat-avg">{global_pct:.0f}%</div></div>
            </div>
        </div>

        <div class="controls">
            <div class="tab-group">
                <button class="tab active" data-bloc="matin" onclick="setBloc('matin')">☀ Bloc Matin</button>
                <button class="tab" data-bloc="apmidi" onclick="setBloc('apmidi')">◑ Bloc Après-midi</button>
            </div>
            <div class="divider"></div>
            <div class="tab-group">
                <button class="tab active" data-view="salle" onclick="setView('salle')">Par Salle</button>
                <button class="tab" data-view="filiere" onclick="setView('filiere')">Par Filière</button>
            </div>
            <div class="search-wrap">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
                <input class="search" id="search" placeholder="Salle, filière…" oninput="render()" />
            </div>
        </div>

        <div class="import-bar">
            <span class="import-title">📥 Importer :</span>
            <button class="btn btn-photo" onclick="document.getElementById('file-photo').click()">📷 Scanner Photo</button>
            <input type="file" id="file-photo" accept="image/*" onchange="handlePhoto(event)" />
            <button class="btn btn-excel" onclick="document.getElementById('file-excel').click()">📊 Importer Excel</button>
            <input type="file" id="file-excel" accept=".xlsx,.xls,.csv" onchange="handleExcel(event)" />
            <div id="import-status" class="import-status">Prêt pour l'importation.</div>
            <button class="btn btn-lancer" onclick="runGreedy()">🚀 Lancer Greedy</button>
            <div id="ocr-progress" style="display:none; margin-left:10px;"><div class="progress-bar"><div class="progress-fg" id="progress-fg" style="width:0%"></div></div></div>
        </div>

        <div class="legend">
            <div class="legend-item"><div class="legend-dot" style="background:#F5B942"></div>L1</div>
            <div class="legend-item"><div class="legend-dot" style="background:#3DAD7A"></div>L2</div>
            <div class="legend-item"><div class="legend-dot" style="background:#4F86D6"></div>L3</div>
            <div class="legend-item"><div class="legend-dot" style="background:#9B5DE5"></div>M</div>
            <div class="legend-sep">
                <div class="fill-legend"><div class="fill-dot" style="background:#3DAD7A"></div>&lt;80%</div>
                <div class="fill-legend"><div class="fill-dot" style="background:#F5A623"></div>80–89%</div>
                <div class="fill-legend"><div class="fill-dot" style="background:#D94040"></div>≥90%</div>
            </div>
        </div>

        <div id="section-info" class="section-info"></div>
        <div id="main-content"></div>

        <div class="import-section" id="import-section" style="display:none">
            <div class="import-section-title"><span>📋 Données Importées</span><span id="import-badge" class="badge-count">0</span></div>
            <div class="json-panel">
                <div class="json-header">
                    <span class="json-header-title" id="import-source-label">Source : —</span>
                    <button class="btn-save" onclick="saveImportedData()">💾 Enregistrer Filières</button>
                </div>
                <div id="img-preview-wrap" style="display:none;padding:12px 18px;border-bottom:1px solid var(--border);background:var(--surface2)">
                    <img id="img-preview" class="preview-img" src="" alt="preview" />
                </div>
                <div class="table-wrap">
                    <table id="import-table"><thead id="import-thead"></thead><tbody id="import-tbody"></tbody></table>
                </div>
            </div>
        </div>

        <footer>
            <span>ENIS — Session Examens 2026 · Greedy Optimisé</span>
            <span>{time.strftime("%d/%m/%Y %H:%M")} · Généré automatiquement</span>
        </footer>
    </div>

    <script>
        const DATA = {{ matin: {json.dumps(s_matin)}, apmidi: {json.dumps(s_apmidi)} }};
        let currentBloc = 'matin';
        let currentView = 'salle';
        let importedData = null;

        const NIV_CLS = {{ L1: 'L1', L2: 'L2', L3: 'L3', M: 'M' }};
        function fillClass(p) {{ return p >= 90 ? 'fill-hi' : p >= 80 ? 'fill-mid' : 'fill-low'; }}

        function buildFilieres(salles) {{
            const map = {{}};
            salles.forEach(s => s.groupes.forEach(g => {{
                const key = g.n + '|' + g.f;
                if (!map[key]) map[key] = {{ niveau: g.n, filiere: g.f, total: 0, salles: [] }};
                map[key].total += g.e;
                map[key].salles.push({{ salle: s.id, etu: g.e }});
            }}));
            return Object.values(map).sort((a, b) => a.filiere.localeCompare(b.filiere));
        }}

        function render() {{
            const salles = DATA[currentBloc];
            if (!salles || salles.length === 0) {{
                document.getElementById('main-content').innerHTML = '<div class="empty-state">Aucun résultat dans ce bloc. Importez des données puis lancez l\\'algorithme.</div>';
                return;
            }}
            const q = document.getElementById('search').value.toLowerCase();
            const totalEtu = salles.reduce((s, sa) => s + sa.groupes.reduce((a, g) => a + g.e, 0), 0);
            const avgFill = Math.round(salles.reduce((s, sa) => s + sa.fill, 0) / salles.length) || 0;
            document.getElementById('stat-bloc').textContent = totalEtu;
            document.getElementById('stat-avg').textContent = avgFill + '%';

            const filtered = salles.filter(s => !q || s.id.toLowerCase().includes(q) || s.groupes.some(g => g.f.toLowerCase().includes(q)));
            const info = document.getElementById('section-info');
            const content = document.getElementById('main-content');

            if (currentView === 'salle') {{
                info.textContent = `${{filtered.length}} salle(s) · Bloc ${{currentBloc === 'matin' ? 'Matin' : 'Après-midi'}}`;
                content.innerHTML = `<div class="cards-grid">${{filtered.map(s => `
                    <div class="card">
                        <div class="card-header"><span class="card-id">${{s.id}}</span><span class="card-cap">Cap <span>${{s.cap}}</span></span></div>
                        <div class="fill-bar-bg"><div class="fill-bar-fg ${{fillClass(s.fill)}}" style="width:${{s.fill}}%"></div></div>
                        <div class="fill-row"><span class="fill-label">Remplissage</span><span class="fill-pct" style="color:${{s.fill >= 90 ? '#D94040' : s.fill >= 80 ? '#C67C0D' : '#2D6A4F'}}">${{s.fill}}%</span></div>
                        <div class="groups">${{s.groupes.map(g => `
                            <div class="group-row grp-${{NIV_CLS[g.n] || 'L1'}}">
                                <span class="group-name"><span class="niveau-badge niv-${{NIV_CLS[g.n] || 'L1'}}">${{g.n}}</span>${{g.f}}</span>
                                <span class="group-etu">${{g.e}} <span>étu</span></span>
                            </div>`).join('')}}</div>
                    </div>`).join('')}}</div>`;
            }} else {{
                const filieres = buildFilieres(salles).filter(f => !q || f.filiere.toLowerCase().includes(q));
                info.textContent = `${{filieres.length}} filière(s)`;
                content.innerHTML = `<div class="fil-grid">${{filieres.map(f => `
                    <div class="fil-card">
                        <div class="fil-header"><div><span class="niveau-badge niv-${{NIV_CLS[f.niveau] || 'L1'}}">${{f.niveau}}</span><span class="fil-name">${{f.filiere}}</span></div><span class="fil-total">${{f.total}}</span></div>
                        <div class="fil-chips">${{f.salles.map(s => `<span class="chip">${{s.salle}} <strong>${{s.etu}}</strong></span>`).join('')}}</div>
                    </div>`).join('')}}</div>`;
            }}
        }}

        function setBloc(b) {{ currentBloc = b; document.querySelectorAll('[data-bloc]').forEach(t => t.classList.toggle('active', t.dataset.bloc === b)); render(); }}
        function setView(v) {{ currentView = v; document.querySelectorAll('[data-view]').forEach(t => t.classList.toggle('active', t.dataset.view === v)); render(); }}

        // Client-Side OCR & Excel
        function setStatus(msg, type = '') {{ const el = document.getElementById('import-status'); el.textContent = msg; el.className = 'import-status ' + type; }}

        function handleExcel(event) {{
            const file = event.target.files[0]; if (!file) return;
            setStatus('Lecture Excel...', 'loading');
            const reader = new FileReader();
            reader.onload = function(e) {{
                const wb = XLSX.read(e.target.result, {{type:'binary'}});
                const ws = wb.Sheets[wb.SheetNames[0]];
                const json = XLSX.utils.sheet_to_json(ws);
                if (json.length) showImportTable(json, file.name);
                else setStatus('Fichier vide', 'error');
            }};
            reader.readAsBinaryString(file);
        }}

        function handlePhoto(event) {{
            const file = event.target.files[0]; if (!file) return;
            setStatus('Analyse OCR...', 'loading');
            document.getElementById('ocr-progress').style.display = 'block';
            document.getElementById('img-preview').src = URL.createObjectURL(file);
            document.getElementById('img-preview-wrap').style.display = 'block';
            Tesseract.recognize(file, 'fra+eng', {{ logger: m => {{ if(m.status==='recognizing text') document.getElementById('progress-fg').style.width = (m.progress*100)+'%'; }} }})
            .then(res => {{
                document.getElementById('ocr-progress').style.display = 'none';
                const parsed = parseOCR(res.data.text);
                showImportTable(parsed, file.name);
                setStatus('OCR Terminé', 'success');
            }}).catch(e => setStatus('Erreur OCR', 'error'));
        }}

        function parseOCR(text) {{
            const lines = text.split('\\n'); const res = [];
            lines.forEach(l => {{
                const clean = l.trim();
                if (clean.length < 3) return;
                const m = clean.match(/(L[123M])?\\s*([\\w_]{{3,}})\\s+(\\d+)/i);
                if (m) {{
                    res.push({{ 
                        Niveau: (m[1] || '?').toUpperCase(), 
                        Filiere: m[2], 
                        Effectif: parseInt(m[3]) 
                    }});
                }}
            }});
            return res;
        }}

        function updateImport(idx, key, val) {{
            if (importedData[idx]) {{
                if (key === 'Effectif') val = parseInt(val) || 0;
                importedData[idx][key] = val;
            }}
        }}

        function delRow(idx) {{
            importedData.splice(idx, 1);
            showImportTable(importedData, document.getElementById('import-source-label').textContent.replace('Source : ', ''));
        }}

        function addRow() {{
            const newItem = importedData.length > 0 ? {{ ...importedData[0] }} : {{ Niveau: 'L1', Filiere: '', Effectif: 0 }};
            Object.keys(newItem).forEach(k => {{ newItem[k] = k === 'Effectif' ? 0 : ''; }});
            importedData.push(newItem);
            showImportTable(importedData, document.getElementById('import-source-label').textContent.replace('Source : ', ''));
        }}

        function showImportTable(data, source) {{
            importedData = data;
            const section = document.getElementById('import-section');
            section.style.display = 'block';
            document.getElementById('import-source-label').textContent = 'Source : ' + source;
            document.getElementById('import-badge').textContent = data ? data.length : 0;
            
            if (!data || data.length === 0) {{
                document.getElementById('import-thead').innerHTML = '<tr><th>Message</th></tr>';
                document.getElementById('import-tbody').innerHTML = '<tr><td>Aucune donnée structurée n\\'a pu être extraite. Vérifiez la qualité de l\\'image.</td></tr>';
            }} else {{
                const cols = Object.keys(data[0]).filter(c => c !== 'JSON');
                document.getElementById('import-thead').innerHTML = `<tr>${{cols.map(c => `<th>${{c}}</th>`).join('')}}<th>Actions</th></tr>`;
                document.getElementById('import-tbody').innerHTML = data.map((r, i) => {{
                    const cells = cols.map(c => {{
                        const v = r[c] ?? '';
                        if (c === 'Niveau') {{
                            const opts = ['L1', 'L2', 'L3', 'M'].map(o => `<option value="${{o}}" ${{o === v ? 'selected' : ''}}>${{o}}</option>`).join('');
                            return `<td><select style="background:transparent;color:inherit;border:1px solid var(--border);border-radius:4px;padding:2px" onchange="updateImport(${{i}},'${{c}}',this.value)">${{opts}}</select></td>`;
                        }}
                        if (c === 'Effectif') {{
                            return `<td><input type="number" style="background:transparent;color:inherit;border:1px solid var(--border);border-radius:4px;padding:2px;width:60px" value="${{v}}" onchange="updateImport(${{i}},'${{c}}',this.value)"></td>`;
                        }}
                        return `<td><input type="text" style="background:transparent;color:inherit;border:1px solid var(--border);border-radius:4px;padding:2px;width:100px" value="${{v}}" onchange="updateImport(${{i}},'${{c}}',this.value)"></td>`;
                    }}).join('');
                    return `<tr>${{cells}}<td><button style="background:transparent;color:var(--danger);border:1px solid var(--danger);border-radius:4px;padding:2px 6px;cursor:pointer" onclick="delRow(${{i}})">✕</button></td></tr>`;
                }}).join('') + `<tr><td colspan="${{cols.length + 1}}"><button class="btn" style="width:100%;margin-top:10px;justify-content:center" onclick="addRow()">+ Ajouter une ligne</button></td></tr>`;
            }}
            section.scrollIntoView({{behavior:'smooth'}});
        }}

        async function saveImportedData() {{
            if(!importedData) return;
            setStatus('Enregistrement...', 'loading');
            try {{
                const res = await fetch('/save-data', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ filiers: importedData }})
                }});
                if(res.ok) alert('Données enregistrées !');
                else throw new Error();
            }} catch(e) {{ alert('Erreur (lancez app.py pour sauvegarder)'); }}
            finally {{ setStatus('Prêt', ''); }}
        }}

        async function runGreedy() {{
            setStatus('Lancement Greedy...', 'loading');
            try {{
                const res = await fetch('/run-algorithm', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ algorithm: 'greedy' }})
                }});
                const result = await res.json();
                if(result.status === 'success') location.reload();
                else alert('Erreur : ' + result.message);
            }} catch(e) {{ alert('Erreur (lancez app.py pour exécuter)'); }}
            finally {{ setStatus('Prêt', ''); }}
        }}

        render();
    </script>
</body>
</html>"""
    
    with open('report.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
    print("  [HTML] Nouveau Dashboard Beige généré : report.html")

# ============================================================
# 6. RECAPITULATIF ET EXECUTION FINALE
# ============================================================

display_bloc("BLOC MATIN", res_morning, dur_morning)
display_bloc("BLOC APRES-MIDI", res_afternoon, dur_afternoon)
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
generate_html_report(res_morning, res_afternoon, dur_morning, dur_afternoon)
