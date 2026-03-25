import sys, json, time, logging, math, os
from collections import defaultdict
from ortools.sat.python import cp_model

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("placement.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("placement")

SEP  = "─" * 70
SEP2 = "═" * 70

def log_section(title):
    log.info(SEP2)
    log.info(f"  {title}")
    log.info(SEP2)

def log_sub(title):
    log.info(SEP)
    log.info(f"  {title}")
    log.info(SEP)

# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════
with open('class.json', 'r', encoding='utf-8') as f:
    rooms_data = json.load(f)
log.info(f"Salles chargées : {len(rooms_data)}")

with open('filier.json', 'r', encoding='utf-8') as f:
    try:
        filieres_raw = json.load(f)
        if not isinstance(filieres_raw, dict) or 'annees' not in filieres_raw:
            if isinstance(filieres_raw, list) and len(filieres_raw) > 0:
                filieres_raw = {"annees": {"custom_import": {"filieres": {
                    f.get('Filiere', f.get('filiere', '')): f.get('Effectif', f.get('effectif', 0))
                    for f in filieres_raw
                }}}}
            else:
                filieres_raw = {"annees": {}}
        log.info("filier.json chargé OK")
    except Exception as e:
        log.error(f"Erreur parsing filier.json : {e}")
        filieres_raw = {"annees": {}}

BUFFER = 3

def load_config():
    global BUFFER
    try:
        if os.path.exists('solver_config.json'):
            with open('solver_config.json', 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                if 'buffer' in cfg:
                    BUFFER = int(cfg['buffer'])
                return cfg
    except Exception as e:
        log.warning(f"Impossible de lire solver_config.json: {e}")
    return None

custom_config = load_config()

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DES LISTES DE FILIÈRES
# ═══════════════════════════════════════════════════════════════════════════════
morning_fils   = []
afternoon_fils = []

annees      = filieres_raw.get('annees', {})
year_labels = {'1ere_annee': 'L1', '2eme_annee': 'L2', '3eme_annee': 'L3', 'master': 'M'}

for annee_key, annee_val in annees.items():
    sub   = annee_val.get('programmes', {}) if annee_key == 'master' else annee_val.get('filieres', {})
    label = year_labels.get(annee_key, annee_key)
    for nom, effectif in sub.items():
        if effectif == 0:
            continue
        filiere = {'name': f"{label} {nom}", 'size': effectif, 'remaining': effectif, 'groups': []}
        if (annee_key in ['master', '1ere_annee'] and nom != 'Ingenieur') \
                or 'Cycle_Preparatoire' in nom or 'custom_import' in annee_key:
            morning_fils.append(filiere)
        else:
            afternoon_fils.append(filiere)

log.info(f"Filières MATIN      : {len(morning_fils)}")
log.info(f"Filières APRES-MIDI : {len(afternoon_fils)}")

EMPTY_MODE = (len(morning_fils) == 0 and len(afternoon_fils) == 0)
if EMPTY_MODE:
    log.warning("Aucune filière trouvée – EMPTY_MODE")

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS BÂTIMENTS
# ═══════════════════════════════════════════════════════════════════════════════
def get_building(salle_name: str) -> str:
    return salle_name[0].upper()

def rooms_by_building(rooms):
    bd = defaultdict(list)
    for ri, r in enumerate(rooms):
        bd[get_building(r['Salle'])].append(ri)
    return bd

# ═══════════════════════════════════════════════════════════════════════════════
# NIVEAUX DE RELAXATION
# ═══════════════════════════════════════════════════════════════════════════════
def get_relaxation_levels():
    if custom_config:
        # Override strict level with custom user parameters
        return [
            dict(min_occ=float(custom_config.get('min_occ', 0.40)),
                 exact_2=bool(custom_config.get('exact_2', True)),
                 balance_slack=int(custom_config.get('balance_slack', 5)),
                 building_bloc=bool(custom_config.get('building_bloc', True)),
                 label="custom user params")
        ]
    return [
        dict(min_occ=0.40, exact_2=True,  balance_slack=5,  building_bloc=True,
             label="strict"),
    ]

RELAXATION_LEVELS = get_relaxation_levels()


def diagnose_infeasibility(bloc_name: str, filieres: list, rooms: list, params: dict):
    """
    Lance des mini-solvers avec une seule contrainte active à la fois.
    Affiche un tableau récapitulatif indiquant quelle contrainte est
    individuellement infaisable, et laquelle est la vraie cause de l'échec.
    """
    log_sub(f"[{bloc_name}] 🔍 DIAGNOSTIC CONTRAINTE PAR CONTRAINTE")
    log.info("  Principe : chaque contrainte est testée SEULE (les autres sont relâchées au maximum).")
    log.info("  Une contrainte marquée [INFEASIBLE] est individuellement bloquante.")
    log.info("  Une contrainte [OK seule] peut quand même bloquer en COMBINAISON avec d'autres.")
    log.info(SEP)

    TIME_LIMIT = 10.0   # secondes par mini-test

    # ── Jeu de paramètres ultra-relâchés (baseline toujours faisable) ─────────
    base = dict(min_occ=0.0, exact_2=False, balance_slack=9999, building_bloc=False)

    # ── Liste des contraintes à tester ───────────────────────────────────────
    constraint_tests = [
        {
            "name":        "min_occ",
            "description": f"Occupation minimale des salles utilisées ≥ {params['min_occ']:.0%}",
            "overrides":   {"min_occ": params['min_occ']},
        },
        {
            "name":        "exact_2",
            "description": f"Exactement 2 filières par salle (exact_2={params['exact_2']})",
            "overrides":   {"exact_2": params['exact_2']},
            "skip_if":     not params['exact_2'],   # inutile si exact_2=False
        },
        {
            "name":        "balance_slack",
            "description": f"Équilibre entre groupes dans une salle (slack={params['balance_slack']})",
            "overrides":   {"balance_slack": params['balance_slack']},
        },
        {
            "name":        "building_bloc",
            "description": f"Toute la filière dans un seul bâtiment (building_bloc={params['building_bloc']})",
            "overrides":   {"building_bloc": params['building_bloc']},
            "skip_if":     not params['building_bloc'],
        },
        {
            "name":        "min_occ + exact_2",
            "description": f"Combinaison min_occ={params['min_occ']:.0%} ET exact_2={params['exact_2']}",
            "overrides":   {"min_occ": params['min_occ'], "exact_2": params['exact_2']},
            "skip_if":     not params['exact_2'],
        },
        {
            "name":        "min_occ + building_bloc",
            "description": f"Combinaison min_occ={params['min_occ']:.0%} ET building_bloc={params['building_bloc']}",
            "overrides":   {"min_occ": params['min_occ'], "building_bloc": params['building_bloc']},
            "skip_if":     not params['building_bloc'],
        },
        {
            "name":        "exact_2 + building_bloc",
            "description": f"Combinaison exact_2={params['exact_2']} ET building_bloc={params['building_bloc']}",
            "overrides":   {"exact_2": params['exact_2'], "building_bloc": params['building_bloc']},
            "skip_if":     not params['exact_2'] and not params['building_bloc'],
        },
        {
            "name":        "TOUTES (niveau complet)",
            "description": "Reproduction exacte du niveau qui a échoué — doit être INFEASIBLE",
            "overrides":   {k: params[k] for k in ['min_occ', 'exact_2', 'balance_slack', 'building_bloc']},
        },
    ]

    results_summary = []

    for test in constraint_tests:
        if test.get("skip_if", False):
            log.info(f"  ⏭  [{test['name']}]  ignoré (inactif à ce niveau)")
            results_summary.append((test['name'], "IGNORÉ", test['description']))
            continue

        # Construire les paramètres du test : base + override
        p = {**base, **test["overrides"]}

        res, status_name, wall = _solve_once(
            bloc_name, filieres, rooms,
            min_occ       = p['min_occ'],
            exact_2       = p['exact_2'],
            balance_slack = p['balance_slack'],
            building_bloc = p['building_bloc'],
            time_limit    = TIME_LIMIT,
        )

        feasible = res is not None
        tag      = "✅ OK seule    " if feasible else "❌ INFEASIBLE  "
        hint     = ""

        if not feasible:
            # Essayer de donner un hint contextuel
            if test['name'] == "min_occ":
                total_s = sum(f['size'] for f in filieres)
                usable  = sum(r['CapaciteTotal'] - BUFFER for r in rooms
                              if (r['CapaciteTotal'] - BUFFER) >= int(r['CapaciteTotal'] * params['min_occ']))
                hint = f"→ Capacité utile={usable} vs étudiants={total_s}"
            elif test['name'] == "building_bloc":
                bd_map = rooms_by_building(rooms)
                bat_caps = {b: sum(rooms[ri]['CapaciteTotal'] - BUFFER for ri in idxs)
                            for b, idxs in bd_map.items()}
                too_big = [f['name'] for f in filieres
                           if all(f['size'] > c for c in bat_caps.values())]
                if too_big:
                    hint = f"→ Filière(s) trop grande(s) pour un seul bâtiment : {too_big}"
            elif test['name'] == "exact_2":
                hint = "→ Nombre de salles insuffisant pour apparier toutes les filières par 2"
            elif test['name'] == "balance_slack":
                hint = f"→ Slack={params['balance_slack']} trop serré pour répartir certains effectifs"

        log.info(f"  {tag}  [{test['name']}]  {test['description']}")
        if hint:
            log.warning(f"              {hint}")

        results_summary.append((test['name'], "OK" if feasible else "INFEASIBLE", test['description']))

    # ── Tableau récapitulatif ─────────────────────────────────────────────────
    log.info(SEP)
    log.info("  RÉCAPITULATIF — Contraintes bloquantes identifiées :")
    log.info(f"  {'Contrainte':<30}  {'Statut':<12}  Description")
    log.info(f"  {'-'*30}  {'-'*12}  {'-'*40}")
    culprits = []
    for name, status, desc in results_summary:
        icon = "❌" if status == "INFEASIBLE" else ("✅" if status == "OK" else "⏭ ")
        log.info(f"  {icon} {name:<28}  {status:<12}  {desc}")
        if status == "INFEASIBLE" and name != "TOUTES (niveau complet)":
            culprits.append(name)

    log.info(SEP)
    if culprits:
        log.error(
            f"  ⚠️  Contrainte(s) individuellement bloquante(s) : {culprits}\n"
            f"     → Relâchez en priorité : {culprits[0]}"
        )
    else:
        log.warning(
            "  ⚠️  Aucune contrainte n'est bloquante SEULE.\n"
            "     → C'est une COMBINAISON de contraintes qui cause l'infaisabilité.\n"
            "     → Regardez les tests 'Combinaison' marqués INFEASIBLE ci-dessus."
        )
    log.info(SEP)


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC PRÉ-SOLVE
# ═══════════════════════════════════════════════════════════════════════════════
def pre_solve_diagnostic(bloc_name, filieres, rooms, params):
    min_occ       = params['min_occ']
    exact_2       = params['exact_2']
    balance_slack = params['balance_slack']
    building_bloc = params['building_bloc']
    label         = params['label']

    log_sub(f"[{bloc_name}] DIAGNOSTIC — niveau '{label}'")

    total_students = sum(f['size'] for f in filieres)
    total_cap      = sum(r['CapaciteTotal'] for r in rooms)
    total_eff_cap  = sum(r['CapaciteTotal'] - BUFFER for r in rooms)

    log.info(f"  Étudiants total        : {total_students}")
    log.info(f"  Capacité brute totale  : {total_cap}")
    log.info(f"  Capacité nette totale  : {total_eff_cap}  (après buffer={BUFFER}/salle)")

    if total_eff_cap < total_students:
        log.error(
            f"  [BLOQUANT] Capacité nette ({total_eff_cap}) < étudiants ({total_students}). "
            f"Manque {total_students - total_eff_cap} places. Impossible quelle que soit la relaxation."
        )
    else:
        log.info(f"  [OK] Capacité nette suffisante  (+{total_eff_cap - total_students} places libres)")

    usable_rooms = [r for r in rooms
                    if (r['CapaciteTotal'] - BUFFER) >= int(r['CapaciteTotal'] * min_occ)]
    unusable_rooms = [r for r in rooms if r not in usable_rooms]
    usable_cap = sum(r['CapaciteTotal'] - BUFFER for r in usable_rooms)

    log.info(f"  Salles utilisables (min_occ={min_occ:.0%}) : "
             f"{len(usable_rooms)}/{len(rooms)}  — capacité utile = {usable_cap}")
    if unusable_rooms:
        names = ', '.join(r['Salle'] for r in unusable_rooms)
        log.warning(f"  [ATTENTION] Salles inutilisables à {min_occ:.0%} : {names}")
    if usable_cap < total_students:
        log.error(
            f"  [BLOQUANT] Capacité utile ({usable_cap}) < étudiants ({total_students}) "
            f"avec min_occ={min_occ:.0%}. "
            f"Manque {total_students - usable_cap} places."
        )
    else:
        log.info(f"  [OK] Capacité utile suffisante  (+{usable_cap - total_students} places)")

    if exact_2:
        avg_cap = total_cap / len(rooms) if rooms else 0
        min_rooms_needed = math.ceil(total_students / (avg_cap * min_occ)) if avg_cap > 0 else 999
        rooms_per_fil = {f['name']: math.ceil(f['size'] / max(1, (avg_cap - BUFFER) / 2))
                         for f in filieres}
        total_room_slots = sum(rooms_per_fil.values())
        log.info(f"  [exact_2=True] Slots-salles nécessaires (heuristique) : {total_room_slots}")
        log.info(f"  [exact_2=True] Salles utilisables disponibles          : {len(usable_rooms)}")
        if total_room_slots > len(usable_rooms):
            log.error(
                f"  [BLOQUANT probable] exact_2=True requiert ~{total_room_slots} salles "
                f"mais seulement {len(usable_rooms)} utilisables. "
                f"→ Passer exact_2=False (niveau suivant) devrait débloquer."
            )
        else:
            log.info(f"  [OK] exact_2=True semble faisable en nombre de salles")

        if building_bloc:
            bd_map = rooms_by_building(rooms)
            for f in filieres:
                f_rooms_needed = rooms_per_fil[f['name']]
                best_bat = max(bd_map.keys(),
                               key=lambda b: sum((rooms[ri]['CapaciteTotal'] - BUFFER)
                                                 for ri in bd_map[b]))
                best_bat_cap = sum((rooms[ri]['CapaciteTotal'] - BUFFER) for ri in bd_map[best_bat])
                best_bat_rooms = len(bd_map[best_bat])
                if f['size'] > best_bat_cap:
                    log.error(
                        f"  [BLOQUANT] Filière '{f['name']}' ({f['size']} etu) > "
                        f"capacité du plus grand bâtiment '{best_bat}' ({best_bat_cap}). "
                        f"building_bloc=True impossible pour cette filière."
                    )
                elif f_rooms_needed > best_bat_rooms:
                    log.warning(
                        f"  [RISQUE] Filière '{f['name']}' ({f['size']} etu) "
                        f"nécessite ~{f_rooms_needed} salles "
                        f"mais le meilleur bâtiment '{best_bat}' n'en a que {best_bat_rooms}."
                    )

    if building_bloc:
        bd_map = rooms_by_building(rooms)
        log.info(f"  Bâtiments détectés : {sorted(bd_map.keys())}")
        bat_caps = {}
        for b, idxs in bd_map.items():
            bc  = sum(rooms[ri]['CapaciteTotal'] for ri in idxs)
            bce = sum(rooms[ri]['CapaciteTotal'] - BUFFER for ri in idxs)
            nb  = len(idxs)
            bat_caps[b] = bce
            log.info(f"    Bâtiment {b} : {nb} salles | cap brute={bc} | cap nette={bce}")

        for f in filieres:
            viable = [b for b, bc in bat_caps.items() if bc >= f['size']]
            if not viable:
                log.error(
                    f"  [BLOQUANT] Filière '{f['name']}' ({f['size']} etu) ne peut tenir "
                    f"dans aucun bâtiment seul. building_bloc=True impossible."
                )
            else:
                log.info(
                    f"  Filière '{f['name']}' ({f['size']} etu) → bâtiments viables : {viable}"
                )

    log.info(f"  balance_slack={balance_slack} : écart max |groupeA - groupeB| dans une salle")
    for f in filieres:
        avg_eff = (sum(r['CapaciteTotal'] - BUFFER for r in rooms) / len(rooms)) if rooms else 1
        n_rooms_f = math.ceil(f['size'] / avg_eff)
        remainder = f['size'] % n_rooms_f if n_rooms_f > 0 else 0
        if remainder > 0 and remainder > balance_slack and exact_2:
            log.warning(
                f"  [RISQUE balance] Filière '{f['name']}' : "
                f"répartition sur ~{n_rooms_f} salles laisse un reste de {remainder} "
                f"(> balance_slack={balance_slack})."
            )

    log.info(SEP)


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC POST-SOLVE
# ═══════════════════════════════════════════════════════════════════════════════
def post_solve_diagnostic(bloc_name, filieres, rooms, results, params):
    if not results:
        log.error(f"[{bloc_name}] POST-SOLVE : aucun résultat à analyser.")
        return

    min_occ       = params['min_occ']
    exact_2       = params['exact_2']
    balance_slack = params['balance_slack']
    building_bloc = params['building_bloc']

    log_sub(f"[{bloc_name}] VÉRIFICATION POST-SOLVE")

    per_room = defaultdict(list)
    for r in results:
        per_room[r['salle']].append(r)

    violations = []

    for salle, entries in per_room.items():
        cap      = entries[0]['real_cap']
        cap_eff  = cap - BUFFER
        tot      = entries[0]['total_in_room']
        n_fils   = len(entries)
        occ_rate = tot / cap if cap > 0 else 0

        if occ_rate < min_occ - 0.001:
            msg = (f"SALLE {salle} : occupation {occ_rate:.1%} < min_occ {min_occ:.0%} "
                   f"({tot}/{cap} etu)")
            log.error(f"  [VIOLATION min_occ]    {msg}")
            violations.append(msg)

        if tot > cap_eff:
            msg = (f"SALLE {salle} : {tot} etu > capacité nette {cap_eff} "
                   f"(brute={cap}, buffer={BUFFER})")
            log.error(f"  [VIOLATION cap_eff]    {msg}")
            violations.append(msg)

        if exact_2 and n_fils != 2:
            msg = f"SALLE {salle} : {n_fils} filière(s) au lieu de 2 exactement"
            log.error(f"  [VIOLATION exact_2]    {msg}")
            violations.append(msg)

        if not exact_2 and n_fils > 2:
            msg = f"SALLE {salle} : {n_fils} filières > maximum autorisé (2)"
            log.error(f"  [VIOLATION max_2]      {msg}")
            violations.append(msg)

        if n_fils == 2:
            s1, s2 = entries[0]['size'], entries[1]['size']
            ecart  = abs(s1 - s2)
            if ecart > balance_slack:
                msg = (f"SALLE {salle} : écart {ecart} > balance_slack {balance_slack} "
                       f"({entries[0]['filiere']}={s1} vs {entries[1]['filiere']}={s2})")
                log.error(f"  [VIOLATION balance]    {msg}")
                violations.append(msg)

    if building_bloc:
        fil_bats = defaultdict(set)
        for r in results:
            fil_bats[r['filiere']].add(r['bat'])
        for fil_name, bats in fil_bats.items():
            if len(bats) > 1:
                msg = f"Filière '{fil_name}' répartie sur bâtiments {bats}"
                log.error(f"  [VIOLATION building_bloc] {msg}")
                violations.append(msg)

    placed_per_fil = defaultdict(int)
    for r in results:
        placed_per_fil[r['filiere']] += r['size']
    for f in filieres:
        placed = placed_per_fil.get(f['name'], 0)
        if placed != f['size']:
            msg = f"Filière '{f['name']}' : {placed} placés sur {f['size']}"
            log.error(f"  [VIOLATION couverture] {msg}")
            violations.append(msg)

    if not violations:
        log.info(f"  [OK] Toutes les contraintes respectées — 0 violation.")
    else:
        log.error(f"  {len(violations)} violation(s) détectée(s) dans la solution !")

    log.info(SEP)


# ═══════════════════════════════════════════════════════════════════════════════
# SOLVER (tentative unique)
# ═══════════════════════════════════════════════════════════════════════════════
def _solve_once(bloc_name, filieres, rooms,
                min_occ, exact_2, balance_slack, building_bloc, optimize_rooms=True,
                time_limit=20.0, attempt=1):
    nf = len(filieres)
    nr = len(rooms)

    model = cp_model.CpModel()

    x = {(fi, ri): model.NewIntVar(0, filieres[fi]['size'], f"x_{fi}_{ri}")
         for fi in range(nf) for ri in range(nr)}

    room_used = [model.NewBoolVar(f"ru_{ri}") for ri in range(nr)]

    fil_present = {}
    for fi in range(nf):
        for ri in range(nr):
            fp = model.NewBoolVar(f"fp_{fi}_{ri}")
            fil_present[(fi, ri)] = fp
            model.Add(x[(fi, ri)] >  0).OnlyEnforceIf(fp)
            model.Add(x[(fi, ri)] == 0).OnlyEnforceIf(fp.Not())

    for fi in range(nf):
        model.Add(sum(x[(fi, ri)] for ri in range(nr)) == filieres[fi]['size'])

    for ri in range(nr):
        cap_total = rooms[ri]['CapaciteTotal']
        cap_eff   = cap_total - BUFFER
        occ_ri    = sum(x[(fi, ri)] for fi in range(nf))

        model.Add(occ_ri >  0).OnlyEnforceIf(room_used[ri])
        model.Add(occ_ri == 0).OnlyEnforceIf(room_used[ri].Not())
        model.Add(occ_ri <= cap_eff)
        model.Add(occ_ri >= int(cap_total * min_occ)).OnlyEnforceIf(room_used[ri])

        fil_count_ri = sum(fil_present[(fi, ri)] for fi in range(nf))
        if exact_2:
            model.Add(fil_count_ri == 2).OnlyEnforceIf(room_used[ri])
        else:
            model.Add(fil_count_ri >= 1).OnlyEnforceIf(room_used[ri])
            model.Add(fil_count_ri <= 2).OnlyEnforceIf(room_used[ri])

        for fi in range(nf):
            model.Add(2 * x[(fi, ri)] - occ_ri <=  balance_slack).OnlyEnforceIf(fil_present[(fi, ri)])
            model.Add(occ_ri - 2 * x[(fi, ri)] <=  balance_slack).OnlyEnforceIf(fil_present[(fi, ri)])

    if building_bloc:
        bd_map    = rooms_by_building(rooms)
        buildings = sorted(bd_map.keys())
        fil_in_building = {}
        for fi in range(nf):
            for b in buildings:
                fib      = model.NewBoolVar(f"fib_{fi}_{b}")
                fil_in_building[(fi, b)] = fib
                any_in_b = [fil_present[(fi, ri)] for ri in bd_map[b]]
                model.AddMaxEquality(fib, any_in_b)
            model.Add(sum(fil_in_building[(fi, b)] for b in buildings) <= 1)

    if optimize_rooms:
        model.Minimize(sum(room_used))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers  = 16
    solver.parameters.random_seed = attempt
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return None, solver.StatusName(status), solver.WallTime()

    results = []
    fil_building_assigned = {}
    for ri in range(nr):
        if solver.Value(room_used[ri]):
            b_letter = get_building(rooms[ri]['Salle'])
            tot = sum(solver.Value(x[(fi, ri)]) for fi in range(nf))
            for fi in range(nf):
                val = solver.Value(x[(fi, ri)])
                if val > 0:
                    prev_b = fil_building_assigned.get(fi)
                    if prev_b is None:
                        fil_building_assigned[fi] = b_letter
                    elif prev_b != b_letter and building_bloc:
                        log.error(
                            f"[{bloc_name}] BUILDING-BLOC VIOLATION : "
                            f"'{filieres[fi]['name']}' dans '{prev_b}' ET '{b_letter}'!"
                        )
                    results.append({
                        'salle':         rooms[ri]['Salle'],
                        'bat':           b_letter,
                        'real_cap':      rooms[ri]['CapaciteTotal'],
                        'eff_cap':       rooms[ri]['CapaciteTotal'] - BUFFER,
                        'filiere':       filieres[fi]['name'],
                        'size':          val,
                        'total_in_room': tot,
                    })

    return results, solver.StatusName(status), solver.WallTime()


# ═══════════════════════════════════════════════════════════════════════════════
# SOLVER AVEC FALLBACK AUTOMATIQUE
# ═══════════════════════════════════════════════════════════════════════════════
def greedy_solve(bloc_name: str, filieres: list, rooms: list, attempt: int = 1):
    log_section(f"BLOC {bloc_name}")

    total_students = sum(f['size'] for f in filieres)
    total_capacity = sum(r['CapaciteTotal'] for r in rooms)
    log.info(f"  Étudiants  : {total_students}")
    log.info(f"  Capacité   : {total_capacity}")
    log.info(f"  Filières   : {len(filieres)}")
    log.info(f"  Salles     : {len(rooms)}")

    log.info("  Liste des filières :")
    for f in sorted(filieres, key=lambda x: -x['size']):
        bar = '█' * (f['size'] // 10)
        log.info(f"    {f['name']:<25} {f['size']:>4} etu  {bar}")

    if total_capacity < total_students:
        log.error(
            f"  IMPOSSIBLE : capacité ({total_capacity}) < étudiants ({total_students}). "
            f"Manque {total_students - total_capacity} places."
        )
        return [], RELAXATION_LEVELS[0]

    for level_idx, params in enumerate(RELAXATION_LEVELS):
        label = params['label']

        log_sub(f"[{bloc_name}] TENTATIVE niveau {level_idx} — '{label}'")
        log.info(f"  min_occ={params['min_occ']:.0%}  |  "
                 f"exact_2={params['exact_2']}  |  "
                 f"balance_slack={params['balance_slack']}  |  "
                 f"building_bloc={params['building_bloc']}")

        pre_solve_diagnostic(bloc_name, filieres, rooms, params)

        t0 = time.time()
        results, status_name, wall_time = _solve_once(
            bloc_name, filieres, rooms,
            min_occ       = params['min_occ'],
            exact_2       = params['exact_2'],
            balance_slack = params['balance_slack'],
            building_bloc = params['building_bloc'],
            optimize_rooms= params.get('optimize_rooms', True),
            time_limit    = 20.0,
            attempt       = attempt,
        )
        elapsed = time.time() - t0

        log.info(f"  ▶ Statut solver : {status_name}  |  durée wall={wall_time:.2f}s  elapsed={elapsed:.2f}s")

        if results is None:
            log.warning(f"  ✗ Échec au niveau {level_idx} ({label})")
            # ── Diagnostic contrainte par contrainte ──────────────────────────
            # diagnose_infeasibility(bloc_name, filieres, rooms, params)

            if level_idx + 1 < len(RELAXATION_LEVELS):
                next_p = RELAXATION_LEVELS[level_idx + 1]
                changes = []
                for k in ['min_occ', 'exact_2', 'balance_slack', 'building_bloc']:
                    if params[k] != next_p[k]:
                        changes.append(f"{k}: {params[k]} → {next_p[k]}")
                log.info(f"    ↳ Prochain niveau '{next_p['label']}' : {', '.join(changes)}")
            continue

        if level_idx == 0:
            log.info(f"  ✓ Solution STRICTE trouvée — toutes les contraintes respectées.")
        else:
            log.warning(
                f"  ✓ Solution trouvée au niveau de relaxation {level_idx} ('{label}')."
            )
            log.warning(f"    Contraintes relâchées par rapport au niveau strict :")
            strict = RELAXATION_LEVELS[0]
            for k in ['min_occ', 'exact_2', 'balance_slack', 'building_bloc']:
                if strict[k] != params[k]:
                    log.warning(f"      {k}: {strict[k]} → {params[k]}")

        post_solve_diagnostic(bloc_name, filieres, rooms, results, params)

        log_sub(f"[{bloc_name}] RÉSUMÉ PLACEMENT")
        placed_in  = defaultdict(lambda: {'bat': None, 'salles': [], 'placed': 0})
        for r in results:
            placed_in[r['filiere']]['bat']    = r['bat']
            placed_in[r['filiere']]['placed'] += r['size']
            placed_in[r['filiere']]['salles'].append(r['salle'])

        for f in sorted(filieres, key=lambda x: -x['size']):
            info = placed_in.get(f['name'])
            if info and info['placed'] == f['size']:
                salles_str = ', '.join(sorted(set(info['salles'])))
                log.info(
                    f"  ✓ {f['name']:<25} {f['size']:>4} etu  "
                    f"bâtiment={info['bat']}  salles=[{salles_str}]"
                )
            else:
                placed = info['placed'] if info else 0
                log.error(f"  ✗ {f['name']:<25} {placed:>4}/{f['size']} etu  NON PLACÉ COMPLÈTEMENT")

        total_placed = sum(r['size'] for r in results)
        n_salles     = len(set(r['salle'] for r in results))
        log.info(f"  Salles utilisées : {n_salles}")
        log.info(f"  Étudiants placés : {total_placed}/{total_students}")

        return results, params

    log.error(
        f"[{bloc_name}] ÉCHEC TOTAL — tous les {len(RELAXATION_LEVELS)} niveaux ont échoué. "
        f"Vérifiez les données des salles."
    )
    return [], RELAXATION_LEVELS[-1]


def solve_with_timer(name, filieres, rooms, attempt=1):
    start           = time.time()
    res, win_params = greedy_solve(name, filieres, rooms, attempt)
    dur             = time.time() - start
    return res, dur, win_params


# ═══════════════════════════════════════════════════════════════════════════════
# EXÉCUTION
# ═══════════════════════════════════════════════════════════════════════════════
target = sys.argv[1] if len(sys.argv) > 1 else 'all'

res_morning, dur_morning, params_morning = [], 0, RELAXATION_LEVELS[0]
res_afternoon, dur_afternoon, params_afternoon = [], 0, RELAXATION_LEVELS[0]

if not EMPTY_MODE:
    if target in ['all', 'matin']:
        for attempt in range(1, 4):
            res_morning, dur_morning, params_morning = solve_with_timer("MATIN", morning_fils, rooms_data, attempt)
            if res_morning:
                break
            if attempt < 3:
                log.warning(f"  [RETRY] Tentative MATIN {attempt} échouée, on recommence...")
                
    if target in ['all', 'apmidi']:
        for attempt in range(1, 4):
            res_afternoon, dur_afternoon, params_afternoon = solve_with_timer("APRES-MIDI", afternoon_fils, rooms_data, attempt)
            if res_afternoon:
                break
            if attempt < 3:
                log.warning(f"  [RETRY] Tentative APRES-MIDI {attempt} échouée, on recommence...")


# ═══════════════════════════════════════════════════════════════════════════════
# AFFICHAGE
# ═══════════════════════════════════════════════════════════════════════════════
def get_stats(results):
    if not results:
        return 0, 0
    return len(set(r['salle'] for r in results)), sum(r['size'] for r in results)


def display_bloc(bloc_name, results, duration, win_params):
    if not results:
        if (target in ['all', 'matin'] and bloc_name == "BLOC MATIN") or \
           (target in ['all', 'apmidi'] and bloc_name == "BLOC APRES-MIDI"):
            print(f"\n  Aucun résultat pour {bloc_name}.")
        return

    per_room = defaultdict(list)
    for r in results:
        per_room[r['salle']].append(r)

    salles_sorted   = sorted(per_room.keys(), key=lambda s: (s[0], s))
    nb_rooms, total_stu = get_stats(results)

    print("=" * 75)
    print(f"  {bloc_name} | Durée: {duration:.4f}s")
    print(f"  Mode : {win_params.get('label','?')} "
          f"| min_occ={win_params.get('min_occ',0):.0%} "
          f"| building_bloc={win_params.get('building_bloc','?')} "
          f"| exact_2={win_params.get('exact_2','?')} "
          f"| balance_slack={win_params.get('balance_slack','?')}")
    print("=" * 75)
    print(f"\n  {'Salle':<6}  {'Cap':>4}  {'Total':>8}  {'Taux':>5}  {'Filières / Groupes'}")
    print(f"  {'-'*6}  {'-'*4}  {'-'*8}  {'-'*5}  {'-'*50}")

    prev_bat = None
    for s_name in salles_sorted:
        ents     = per_room[s_name]
        real_cap = ents[0]['real_cap']
        tot      = ents[0]['total_in_room']
        pct      = (tot / real_cap * 100) if real_cap > 0 else 0

        bat = s_name[0]
        if bat != prev_bat:
            if prev_bat is not None:
                print()
            prev_bat = bat

        bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
        print(f"  {s_name:<6}  {real_cap:>4}  {tot:>8}  {pct:>4.0f}%  [{bar}]")
        for e in ents:
            print(f"         {'':>14}  {e['filiere']:<22} {e['size']:>4} etu")

    print(f"\n  TOTAL {bloc_name}:")
    print(f"  - Salles utilisées   : {nb_rooms}")
    print(f"  - Étudiants placés   : {total_stu}")
    print(f"  - Temps d'exécution : {duration:.4f}s")
    print("=" * 75 + "\n")


display_bloc("BLOC MATIN",      res_morning,   dur_morning,   params_morning)
display_bloc("BLOC APRES-MIDI", res_afternoon, dur_afternoon, params_afternoon)


# ═══════════════════════════════════════════════════════════════════════════════
# SAUVEGARDE JSON
# ═══════════════════════════════════════════════════════════════════════════════
def save_results_to_json(morning_res, afternoon_res, params_m, params_a, tgt):
    def to_bloc(res):
        if not res: return []
        bloc = []
        for s_name in sorted(set(r['salle'] for r in res), key=lambda s: (s[0], s)):
            ents = [r for r in res if r['salle'] == s_name]
            bloc.append({
                'id':      s_name,
                'cap':     ents[0]['real_cap'],
                'fill':    int(ents[0]['total_in_room'] / ents[0]['real_cap'] * 100)
                           if ents[0]['real_cap'] > 0 else 0,
                'groupes': [{'n': r['filiere'].split()[0],
                             'f': ' '.join(r['filiere'].split()[1:]),
                             'e': r['size']} for r in ents],
            })
        return bloc

    old_data = {}
    try:
        with open('placement.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except:
        pass

    matin_data = old_data.get('matin', []) if tgt == 'apmidi' else to_bloc(morning_res)
    apmidi_data = old_data.get('apmidi', []) if tgt == 'matin' else to_bloc(afternoon_res)
    rel_matin = old_data.get('relaxation_matin', '?') if tgt == 'apmidi' else params_m.get('label', '?')
    rel_apmidi = old_data.get('relaxation_apmidi', '?') if tgt == 'matin' else params_a.get('label', '?')
    p_matin = old_data.get('params_matin', {}) if tgt == 'apmidi' else {k: v for k, v in params_m.items() if k != 'label'}
    p_apmidi = old_data.get('params_apmidi', {}) if tgt == 'matin' else {k: v for k, v in params_a.items() if k != 'label'}

    data = {
        'matin':             matin_data,
        'apmidi':            apmidi_data,
        'relaxation_matin':  rel_matin,
        'relaxation_apmidi': rel_apmidi,
        'params_matin':      p_matin,
        'params_apmidi':     p_apmidi,
        'timestamp':         time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open('placement.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    log.info("Résultats sauvegardés → placement.json")
    print("  [JSON] Résultats sauvegardés dans : placement.json")


save_results_to_json(res_morning, res_afternoon, params_morning, params_afternoon, target)