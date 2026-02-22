
import sys, json, math, random, time
sys.stdout.reconfigure(encoding='utf-8')
from ortools.sat.python import cp_model
from collections import defaultdict

# ============================================================
# 1. CHARGEMENT
# ============================================================

with open('class.json',  'r', encoding='utf-8') as f:
    rooms_data = json.load(f)

with open('filier.json', 'r', encoding='utf-8') as f:
    filieres_raw = json.load(f)

BUFFER       = 4    # buffer securite par salle
MAX_GRP_SIZE = 20   # effectif max d'un sous-groupe dans une salle

# ============================================================
# 2. CONSTRUCTION DES GROUPES
# ============================================================

def split_groups(name, effectif, meta, annee_label):
    """Decoupe une filiere en sous-groupes de MAX_GRP_SIZE max."""
    n    = max(1, math.ceil(effectif / MAX_GRP_SIZE))
    base = effectif // n
    rem  = effectif % n
    # On ajoute le prefixe d'annee (L1, L2, etc.) au nom de la filiere pour les distinguer
    full_filiere_name = f"{annee_label} {name}"
    return [
        {
            'id': f"{annee_label}_{name}_{i}", 
            'name': f"{annee_label} {name} G{i+1}", 
            'filiere': full_filiere_name, 
            'size': base + (1 if i < rem else 0),
            'meta': meta
        }
        for i in range(n)
    ]

morning_groups = []   # Ing + Prepa + Masters
afternoon_groups = [] # Licences L1/L2/L3

annees = filieres_raw['annees']

# Categorisation meta et labels d'annee
meta_map = {'master': 'Master', '1ere_annee': 'Licence', '2eme_annee': 'Licence', '3eme_annee': 'Licence'}
year_labels = {'1ere_annee': 'L1', '2eme_annee': 'L2', '3eme_annee': 'L3', 'master': 'M'}

for annee_key, annee_val in annees.items():
    sub = annee_val.get('programmes', {}) if annee_key == 'master' else annee_val.get('filieres', {})
    annee_label = year_labels.get(annee_key, annee_key)
    
    for nom, effectif in sub.items():
        if effectif == 0: continue
        
        meta = "Licence"
        if annee_key == 'master': meta = "Master"
        elif 'Ingenieur' in nom:  meta = "Ing"
        elif 'Cycle_Preparatoire' in nom: meta = "Prepa"

        grps = split_groups(nom, effectif, meta, annee_label)
        
        if annee_key in ['master', '1ere_annee'] or 'Ingenieur' in nom or 'Cycle_Preparatoire' in nom:
            morning_groups.extend(grps)
        else:
            afternoon_groups.extend(grps)

# ============================================================
# 3. AFFICHAGE DU RESUME
# ============================================================

total_cap = sum(r['CapaciteTotal'] - BUFFER for r in rooms_data)

print("=" * 70)
print("       PLACEMENT FIXE DES EXAMENS - SYSTEME DE BLOCS")
print("=" * 70)
print(f"  Salles disponibles  : {len(rooms_data)} salles | Capacite totale : {total_cap} places")
print()
print(f"  BLOC MATIN      (08h30 + 10h15) : "
      f"{sum(g['size'] for g in morning_groups):>5} etudiants | "
      f"{len(morning_groups):>3} groupes")
print(f"  BLOC APRES-MIDI (12h00 + 13h45) : "
      f"{sum(g['size'] for g in afternoon_groups):>5} etudiants | "
      f"{len(afternoon_groups):>3} groupes")
print(f"  TOTAL                           : "
      f"{sum(g['size'] for g in morning_groups+afternoon_groups):>5} etudiants")
print("=" * 70)
print()

# ============================================================
# 4. MODELE CP-SAT
# ============================================================

def solve_bloc(bloc_name, groups, rooms, time_limit=12, seed=None):
    """
    Resoud l'affectation salle pour un bloc.
    Retourne une liste de dicts : {salle, cap, filiere, groupe, size}
    """
    if seed is None:
        seed = random.randint(0, 999999)
    
    nr = len(rooms)
    ng = len(groups)

    if ng == 0:
        print(f"  [SKIP] {bloc_name} : aucun groupe.")
        return []

    model = cp_model.CpModel()

    # --------------------------------------------------
    # VARIABLES
    # --------------------------------------------------

    # x[gi, ri] = 1 si groupe gi est dans salle ri
    x = {}
    for gi in range(ng):
        for ri in range(nr):
            x[(gi, ri)] = model.NewBoolVar(f"x_{gi}_{ri}")

    # room_used[ri] = 1 si salle ri est utilisee
    room_used = [model.NewBoolVar(f"ru_{ri}") for ri in range(nr)]

    # occ[ri] = occupation totale de la salle ri
    occ = [model.NewIntVar(0, rooms[ri]['CapaciteTotal'], f"occ_{ri}") for ri in range(nr)]

    # Filieres uniques pour la contrainte max 2 filieres/salle
    filieres_list = list(set(g['filiere'] for g in groups))
    fil_idx  = {f: i for i, f in enumerate(filieres_list)}
    nf = len(filieres_list)

    # fil_present[fi, ri] = 1 si filiere fi presente dans salle ri
    fil_present = {}
    for fi in range(nf):
        for ri in range(nr):
            fil_present[(fi, ri)] = model.NewBoolVar(f"fp_{fi}_{ri}")

    # Meta-categories pour les filieres
    # On cree une map filiere -> meta
    fil_to_meta = {}
    for g in groups:
        fil_to_meta[g['filiere']] = g['meta']
    
    meta_list = sorted(list(set(fil_to_meta.values())))
    nm = len(meta_list)
    meta_idx = {m: i for i, m in enumerate(meta_list)}
    
    # meta_present[mi, ri] = 1 si meta-categorie mi presente dans salle ri
    meta_present = {}
    for mi in range(nm):
        for ri in range(nr):
            meta_present[(mi, ri)] = model.NewBoolVar(f"mp_{mi}_{ri}")

    # --------------------------------------------------
    # CONTRAINTES HARD
    # --------------------------------------------------

    # C1 : Chaque groupe dans exactement une salle
    for gi in range(ng):
        model.Add(sum(x[(gi, ri)] for ri in range(nr)) == 1)

    # C2 : Occupation = somme des effectifs    +    Capacite max respectee
    for ri, r in enumerate(rooms):
        cap = r['CapaciteTotal'] - BUFFER
        model.Add(occ[ri] == sum(x[(gi, ri)] * groups[gi]['size'] for gi in range(ng)))
        model.Add(occ[ri] <= cap)

    # C3 : Lier room_used a l'occupation
    for ri in range(nr):
        nb_in = sum(x[(gi, ri)] for gi in range(ng))
        model.Add(nb_in >= 1).OnlyEnforceIf(room_used[ri])
        model.Add(nb_in == 0).OnlyEnforceIf(room_used[ri].Not())
        model.Add(occ[ri] == 0).OnlyEnforceIf(room_used[ri].Not())

    # C4 : Max 2 filieres differentes par salle
    for ri in range(nr):
        # Liaison fil_present : fi est present dans ri si au moins un de ses groupes y est
        for fi, fname in enumerate(filieres_list):
            grps_of_f = [gi for gi, g in enumerate(groups) if g['filiere'] == fname]
            if grps_of_f:
                model.AddMaxEquality(fil_present[(fi, ri)], [x[(gi, ri)] for gi in grps_of_f])
            else:
                model.Add(fil_present[(fi, ri)] == 0)
        
        # Max 2 filieres/salle
        model.Add(sum(fil_present[(fi, ri)] for fi in range(nf)) <= 2)
        
        # Liaison meta_present : mi est present dans ri si au moins une filiere de meta mi y est
        for mi, m_name in enumerate(meta_list):
            fils_of_m = [fi for fi, f_name in enumerate(filieres_list) if fil_to_meta[f_name] == m_name]
            if fils_of_m:
                model.AddMaxEquality(meta_present[(mi, ri)], [fil_present[(fi, ri)] for fi in fils_of_m])
            else:
                model.Add(meta_present[(mi, ri)] == 0)

    # --------------------------------------------------
    # FONCTION OBJECTIF (multi-criteres)
    # --------------------------------------------------

    # O1 : Minimiser le nombre de salles utilisees (poids fort)
    num_used = sum(room_used)

    # O2 : Maximiser l'occupation totale (remplir les salles)
    total_occ = sum(occ[ri] for ri in range(nr))

    # O3 : Bonus de regroupement : 2 groupes de la meme filiere dans la meme salle
    #      Pour chaque paire (gi, gj) de la meme filiere, bonus si dans la meme salle
    same_fil_bonus = []
    groupe_by_fil = defaultdict(list)
    for gi, g in enumerate(groups):
        groupe_by_fil[g['filiere']].append(gi)

    for fname, gidx_list in groupe_by_fil.items():
        for k in range(len(gidx_list)):
            for l in range(k+1, len(gidx_list)):
                gi, gj = gidx_list[k], gidx_list[l]
                for ri in range(nr):
                    # bonus_var = x[gi,ri] AND x[gj,ri]
                    b = model.NewBoolVar(f"sfb_{gi}_{gj}_{ri}")
                    model.AddBoolAnd([x[(gi, ri)], x[(gj, ri)]]).OnlyEnforceIf(b)
                    model.AddBoolOr([x[(gi, ri)].Not(), x[(gj, ri)].Not()]).OnlyEnforceIf(b.Not())
                    same_fil_bonus.append(b)

    # O4 : Bonus batiment : paire de salles du meme batiment toutes deux utilisees
    bat_groups = defaultdict(list)
    for ri, r in enumerate(rooms):
        bat_groups[r['Salle'][0]].append(ri)

    bat_bonus = []
    for bat, r_list in bat_groups.items():
        for a in range(len(r_list)):
            for b_idx in range(a+1, len(r_list)):
                ra, rb = r_list[a], r_list[b_idx]
                pv = model.NewBoolVar(f"bat_{bat}_{a}_{b_idx}")
                model.AddBoolAnd([room_used[ra], room_used[rb]]).OnlyEnforceIf(pv)
                model.AddBoolOr([room_used[ra].Not(), room_used[rb].Not()]).OnlyEnforceIf(pv.Not())
                bat_bonus.append(pv)

    # Poids de l'objectif
    W_rooms  = 2000000
    W_shared = 50000     # Bonus mixite (2 filieres)
    W_mix    = 10000     # Bonus duo favori
    W_sfb    = 5000      # Regroupement meme filiere
    W_occ    = 100       # Remplissage
    W_bal    = 100       # Equilibre (penalite)
    W_bat    = 10        # Proximite batiment

    # 0. Bonus Mixite Generale (Duo de filieres)
    all_shared_vars = []
    for ri in range(nr):
        nb_fils = model.NewIntVar(0, nf, f"nbf_{ri}")
        model.Add(nb_fils == sum(fil_present[(fi, ri)] for fi in range(nf)))
        
        is_shared_ri = model.NewBoolVar(f"is_shared_{ri}")
        model.Add(nb_fils == 2).OnlyEnforceIf(is_shared_ri)
        model.Add(nb_fils != 2).OnlyEnforceIf(is_shared_ri.Not())
        all_shared_vars.append(is_shared_ri)
        
        # CONTRAINTE HARD : Interdit d'avoir une seule filiere par salle
        # Si la salle est utilisee, elle DOIT etre partagee (nb_fil=2)
        model.Add(is_shared_ri == 1).OnlyEnforceIf(room_used[ri])

    # 1. Bonus Mixite Specifique (Paires favorites)
    # PAIRES_FAVORITES = [('Ing', 'Prepa'), ('Master', 'Ing'), ('Prepa', 'Licence')]
    fav_pairs = [('Ing', 'Prepa'), ('Master', 'Ing'), ('Prepa', 'Licence')]
    mix_bonus_vars = []
    for ri in range(nr):
        # Une salle a un bonus de mixite si elle contient EXACTEMENT deux meta-categories
        # ET que ces deux forment une paire favorite.
        nb_metas = model.NewIntVar(0, nm, f"nbm_{ri}")
        model.Add(nb_metas == sum(meta_present[(mi, ri)] for mi in range(nm)))
        
        is_mixed = model.NewBoolVar(f"is_mixed_{ri}")
        model.Add(nb_metas == 2).OnlyEnforceIf(is_mixed)
        model.Add(nb_metas != 2).OnlyEnforceIf(is_mixed.Not())
        
        for p1, p2 in fav_pairs:
            if p1 in meta_idx and p2 in meta_idx:
                m1, m2 = meta_idx[p1], meta_idx[p2]
                match_pair = model.NewBoolVar(f"match_{p1}_{p2}_{ri}")
                model.AddBoolAnd([is_mixed, meta_present[(m1, ri)], meta_present[(m2, ri)]]).OnlyEnforceIf(match_pair)
                model.AddBoolOr([is_mixed.Not(), meta_present[(m1, ri)].Not(), meta_present[(m2, ri)].Not()]).OnlyEnforceIf(match_pair.Not())
                mix_bonus_vars.append(match_pair)

    # 2. Equilibres des effectifs STRICTS (O(N))
    # On impose |2 * size_filiere - total_occ| <= 4 si la salle est partagee (nb_fil=2)
    # Cela garantit que S1-S2 est entre -4 et 4.
    for ri in range(nr):
        for fi, f_name in enumerate(filieres_list):
            grps_of_f = [gi for gi, g in enumerate(groups) if g['filiere'] == f_name]
            s_fi = model.NewIntVar(0, rooms[ri]['CapaciteTotal'], f"s_{fi}_{ri}")
            model.Add(s_fi == sum(x[(gi, ri)] * groups[gi]['size'] for gi in grps_of_f))
            
            # Contrainte diffuse : si shared=1 et s_fi > 0 => |2*s_fi - occ| <= 4
            is_present = fil_present[(fi, ri)]
            active_balance = model.NewBoolVar(f"ab_{fi}_{ri}")
            model.AddBoolAnd([all_shared_vars[ri], is_present]).OnlyEnforceIf(active_balance)
            model.AddBoolOr([all_shared_vars[ri].Not(), is_present.Not()]).OnlyEnforceIf(active_balance.Not())
            
            model.Add(2 * s_fi - occ[ri] <= 4).OnlyEnforceIf(active_balance)
            model.Add(occ[ri] - 2 * s_fi <= 4).OnlyEnforceIf(active_balance)

    # 3. Bruit Aleatoire
    noise = model.NewIntVar(0, 100, f"n_{bloc_name}")
    # Le bruit n'a pas de contrainte, il sera choisi librement pour varier la solution
    # dans le cas ou plusieurs solutions ont le meme score reel.

    total_sfb = sum(same_fil_bonus) if same_fil_bonus else model.NewConstant(0)
    total_bat = sum(bat_bonus)      if bat_bonus      else model.NewConstant(0)
    total_mix = sum(mix_bonus_vars) if mix_bonus_vars else model.NewConstant(0)

    model.Maximize(
        - W_rooms  * num_used
        + W_occ    * total_occ
        + W_sfb    * total_sfb
        + W_bat    * total_bat
        + W_mix    * total_mix
        + noise # Noise tres faible
    )

    # --------------------------------------------------
    # RESOLUTION
    # --------------------------------------------------

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers  = 16
    solver.parameters.log_search_progress = False
    
    # Parametres d'aleatoire
    solver.parameters.random_seed = seed

    print(f"  Resolution {bloc_name} ({ng} groupes, {sum(g['size'] for g in groups)} etu) | Seed: {seed}...")
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"  [ECHEC] {bloc_name} : {status_name}")
        return []

    sol_type = "OPTIMALE" if status == cp_model.OPTIMAL else "REALISABLE"
    print(f"  [OK - {sol_type}] {solver.WallTime():.1f}s")

    # Collecter les resultats
    results = []
    for ri, r in enumerate(rooms):
        if solver.Value(room_used[ri]) != 1:
            continue
        cap = r['CapaciteTotal'] - BUFFER
        assigned = [gi for gi in range(ng) if solver.Value(x[(gi, ri)]) == 1]
        if not assigned:
            continue
        total_in_room = solver.Value(occ[ri])
        for gi in assigned:
            results.append({
                'salle'  : r['Salle'],
                'bat'    : r['Salle'][0],
                'cap'    : cap,
                'filiere': groups[gi]['filiere'],
                'groupe' : groups[gi]['name'],
                'size'   : groups[gi]['size'],
                'total_in_room': total_in_room,
                'pct'    : total_in_room / cap * 100,
            })

    return results

# ============================================================
# 5. RESOLUTION DES DEUX BLOCS
# ============================================================

results_matin = solve_bloc(
    "BLOC MATIN",
    morning_groups,
    rooms_data,
    time_limit=45,
    seed=int(time.time()) % 1000000
)

results_aprem = solve_bloc(
    "BLOC APRES-MIDI",
    afternoon_groups,
    rooms_data,
    time_limit=45,
    seed=(int(time.time()) + 42) % 1000000
)

print()

# ============================================================
# 6. AFFICHAGE DU PLANNING
# ============================================================

def display_bloc(bloc_name, horaires, results, rooms):
    if not results:
        print(f"  Aucun resultat pour {bloc_name}.")
        return

    print("=" * 75)
    print(f"  {bloc_name.upper()}   ({horaires})")
    print("  Planning valable pour TOUTE LA SEMAINE")
    print("=" * 75)

    # Regrouper par salle
    salle_dict = defaultdict(list)
    for e in results:
        salle_dict[e['salle']].append(e)

    # Trier les salles par batiment puis par nom
    salles_sorted = sorted(salle_dict.keys(), key=lambda s: (s[0], s))

    total_stu = 0
    total_cap = 0
    nb_rooms  = len(salles_sorted)

    # en-tete tableau
    print(f"\n  {'Salle':<6}  {'Cap':>4}  {'Effectif':>8}  {'Taux':>5}  {'Filieres / Groupes'}")
    print(f"  {'-'*6}  {'-'*4}  {'-'*8}  {'-'*5}  {'-'*50}")

    prev_bat = None
    for salle in salles_sorted:
        entries = salle_dict[salle]
        cap     = entries[0]['cap']
        tot     = entries[0]['total_in_room']
        pct     = entries[0]['pct']

        total_stu += tot
        total_cap += cap

        # Bar de remplissage
        bar_len = int(pct / 5)
        bar = '#' * bar_len + '.' * (20 - bar_len)

        # Separator de batiment
        bat = salle[0]
        if bat != prev_bat:
            if prev_bat is not None:
                print()
            prev_bat = bat

        # Ligne principale avec barre
        print(f"  {salle:<6}  {cap:>4}  {tot:>8}  {pct:>4.0f}%  [{bar}]")

        # Detail par groupe (indente)
        by_filiere = defaultdict(list)
        for e in entries:
            by_filiere[e['filiere']].append(e)

        for fil, grps in sorted(by_filiere.items()):
            subtotal = sum(g['size'] for g in grps)
            grp_names = ", ".join(g['groupe'] for g in grps)
            print(f"         {'':>14}  {'':>5}  {fil:<22} {subtotal:>4} etu  ({grp_names})")

    # Stats
    global_pct = total_stu / total_cap * 100 if total_cap else 0
    print()
    print(f"  {'='*73}")
    print(f"  {'Salles utilisees':<30}: {nb_rooms}")
    print(f"  {'Etudiants places':<30}: {total_stu}")
    print(f"  {'Capacite mobilisee':<30}: {total_cap} places")
    print(f"  {'Taux global d occupation':<30}: {global_pct:.1f}%")
    print(f"  {'Moyenne par salle':<30}: {total_stu/nb_rooms:.1f} etu/salle")

    # Histogramme de distribution des taux
    hist = defaultdict(int)
    for salle in salles_sorted:
        e0  = salle_dict[salle][0]
        pct = e0['pct']
        bucket = int(pct // 10) * 10
        hist[bucket] += 1
    print(f"\n  Distribution des taux de remplissage :")
    for b in sorted(hist):
        bar = '|' * hist[b]
        print(f"  {b:>3}%-{b+9:>3}% : {bar:<20} ({hist[b]} salles)")

    print()

print()
display_bloc(
    "BLOC MATIN",
    "08h30-09h30  et  10h15-11h15",
    results_matin,
    rooms_data
)

display_bloc(
    "BLOC APRES-MIDI",
    "12h00-13h00  et  13h45-14h45",
    results_aprem,
    rooms_data
)

# ============================================================
# 7. RECAPITULATIF GLOBAL
# ============================================================

def stats(results):
    salles = set(e['salle'] for e in results)
    stu    = sum(e['size'] for e in results)
    cap    = sum(next(r['CapaciteTotal'] - BUFFER for r in rooms_data if r['Salle'] == s)
                 for s in salles)
    return len(salles), stu, cap

ns_m, stu_m, cap_m = stats(results_matin)
ns_a, stu_a, cap_a = stats(results_aprem)

print("=" * 75)
print("  RECAPITULATIF GLOBAL")
print("=" * 75)
print(f"  {'Bloc':<20} {'Salles':>7} {'Etudiants':>10} {'Capacite':>10} {'Taux':>7}")
print(f"  {'-'*20} {'-'*7} {'-'*10} {'-'*10} {'-'*7}")
print(f"  {'Matin (08h30+10h15)':<20} {ns_m:>7} {stu_m:>10} {cap_m:>10} "
      f"{stu_m/cap_m*100:>6.1f}%" if cap_m else "")
print(f"  {'Apres-midi (12h+13h45)':<20} {ns_a:>7} {stu_a:>10} {cap_a:>10} "
      f"{stu_a/cap_a*100:>6.1f}%" if cap_a else "")
total_stu = stu_m + stu_a
total_cap_used = cap_m + cap_a
print(f"  {'-'*20} {'-'*7} {'-'*10} {'-'*10} {'-'*7}")
print(f"  {'TOTAL':<20} {ns_m+ns_a:>7} {total_stu:>10} {total_cap_used:>10} "
      f"{total_stu/total_cap_used*100:>6.1f}%" if total_cap_used > 0 else "")
print("=" * 75)
