import mysql.connector
import os
import json
from ortools.sat.python import cp_model
import time

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        user=os.getenv('DB_USER', 'root'),
        password='',
        database='gestion_examens_s1'
    )

def generate_surveillance():
    t_start = time.time()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id_professeur as id, nom_prenom as full_name, grade, charge_surv FROM professeur")
    profs_db = cursor.fetchall()

    cursor.execute("""SELECT id_matiere, nom_matiere, jour_num, id_professeur, has_examen 
                      FROM matiere WHERE has_examen=1 AND jour_num IS NOT NULL""")
    matieres = cursor.fetchall()

    cursor.execute("SELECT salle_name, type_session, id_filiere1, id_filiere2 FROM salle_filieres")
    salle_filieres = cursor.fetchall()

    cursor.execute("""SELECT id_filaire, jour_num, COUNT(*) as exam_count 
                      FROM matiere WHERE has_examen=1 AND jour_num IS NOT NULL 
                      GROUP BY id_filaire, jour_num""")
    exam_data = cursor.fetchall()

    cursor.close()
    conn.close()

    # ================================================================== #
    # ÉTAPE 1 — DONNÉES DE BASE
    # ================================================================== #
    filiere_counts = {}
    for row in exam_data:
        fid = row['id_filaire']
        jno = row['jour_num']
        if fid not in filiere_counts:
            filiere_counts[fid] = {}
        filiere_counts[fid][jno] = row['exam_count']

    prof_data = {}
    for p in profs_db:
        name = p['full_name']
        if not name or name.strip() == "" or "Non spécifié" in name:
            continue
        # charge_surv = nombre total de SESSIONS à surveiller dans la semaine
        charge = p['charge_surv'] if p['charge_surv'] is not None else 4
        prof_data[p['id']] = {
            'full_name':    name,
            'grade':        p['grade'],
            'charge_surv':  charge,       # sessions totales semaine
            'matieres_days': set()
        }

    for m in matieres:
        pid = m['id_professeur']
        if pid in prof_data and m['jour_num']:
            prof_data[pid]['matieres_days'].add(m['jour_num'])

    # ── TRI PAR CHARGE DESC : les profs avec plus de charge ont la priorité
    # Cela évite que des profs à faible charge (ex: 6) soient sur-utilisés
    # pendant que des profs à forte charge (ex: 10) restent sous-utilisés.
    prof_ids = sorted(prof_data.keys(), key=lambda p: -prof_data[p]['charge_surv'])

    # ================================================================== #
    # ÉTAPE 2 — SLOTS ACTIFS PAR JOUR ET PAR SALLE
    # slot 0=Matin1, 1=Matin2, 2=AprèsMidi1, 3=AprèsMidi2
    # ================================================================== #
    active_slots = {}   # active_slots[day][room] = [liste de slots actifs]
    for day in range(1, 7):
        active_slots[day] = {}
        room_configs = {}
        for r in salle_filieres:
            s_name = r['salle_name']
            t_ses  = r['type_session']
            if s_name not in room_configs:
                room_configs[s_name] = {'matin_slots': 0, 'apmidi_slots': 0}
            c1 = filiere_counts.get(r['id_filiere1'], {}).get(day, 0) if r['id_filiere1'] else 0
            c2 = filiere_counts.get(r['id_filiere2'], {}).get(day, 0) if r['id_filiere2'] else 0
            max_exams = max(c1, c2)
            if t_ses == 'matin':
                room_configs[s_name]['matin_slots'] = max(
                    room_configs[s_name]['matin_slots'], min(max_exams, 2))
            else:
                room_configs[s_name]['apmidi_slots'] = max(
                    room_configs[s_name]['apmidi_slots'], min(max_exams, 2))

        for s_name, cfg in room_configs.items():
            slots = []
            for t in range(cfg['matin_slots']):
                slots.append(t)           # 0 ou 1
            for t in range(cfg['apmidi_slots']):
                slots.append(t + 2)       # 2 ou 3
            if slots:
                active_slots[day][s_name] = slots

    # ================================================================== #
    # ÉTAPE 3 — LISTE DES PROFS OBLIGATOIRES PAR JOUR
    #           + CALCUL DES SESSIONS DISPONIBLES PAR PROF PAR JOUR
    # ================================================================== #
    # sessions_per_day[day] = nombre total de (salle×slot) ce jour
    sessions_per_day = {}
    for day in range(1, 7):
        sessions_per_day[day] = sum(
            len(slots) for slots in active_slots.get(day, {}).values())

    # Pour chaque jour : liste des profs OBLIGATOIRES (ont matière ce jour)
    mandatory_by_day = {day: [] for day in range(1, 7)}
    for p in prof_ids:
        for day in prof_data[p]['matieres_days']:
            if 1 <= day <= 6:
                mandatory_by_day[day].append(p)

    print("\n" + "="*60)
    print("  LISTE DES PROFS OBLIGATOIRES PAR JOUR")
    print("="*60)
    for day in range(1, 7):
        day_name = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'][day-1]
        profs_list = mandatory_by_day[day]
        print(f"\n  {day_name} ({sessions_per_day[day]} sessions actives, "
              f"besoin: {sessions_per_day[day]*2} créneaux-profs) :")
        if profs_list:
            for p in profs_list:
                print(f"    - {prof_data[p]['full_name']:30s} | "
                      f"Grade: {prof_data[p]['grade']:10s} | "
                      f"Charge: {prof_data[p]['charge_surv']} sessions")
        else:
            print("    (aucun prof obligatoire)")

    # ================================================================== #
    # ÉTAPE 4 — DISTRIBUTION DES SESSIONS ET GESTION DU REPORT
    #
    # Logique :
    #   - charge_surv = nb total de sessions à surveiller sur la semaine
    #   - Un prof obligatoire un jour Y doit surveiller ce jour-là
    #   - On compte d'abord combien de sessions seront consommées
    #     les jours obligatoires (sessions_per_day × 2 profs)
    #   - Si charge restante après les jours obligatoires > 0
    #     → le prof est disponible les jours suivants aussi
    #   - Si un jour manque de profs → on emprunte du lendemain
    # ================================================================== #

    # charge_restante[p] = sessions encore disponibles (évolue dynamiquement)
    charge_restante = {p: prof_data[p]['charge_surv'] for p in prof_ids}

    # available_per_day[day] = set de prof_ids disponibles ce jour
    # (= obligatoires + ceux avec charge restante qui peuvent venir)
    available_per_day = {day: set() for day in range(1, 7)}

    # D'abord, marquer les profs obligatoires
    for day in range(1, 7):
        for p in mandatory_by_day[day]:
            available_per_day[day].add(p)

    # ── RÈGLE DE DISTRIBUTION ───────────────────────────────────────────────
    # 1. Les profs OBLIGATOIRES sont marqués disponibles leur jour obligatoire.
    # 2. Les profs à FORTE CHARGE (charge >= nb sessions actives d'un jour)
    #    sont disponibles sur TOUS les jours actifs : ils ont la capacité
    #    d'absorber plusieurs sessions par jour → pas de limitation arbitraire.
    # 3. Les profs à CHARGE MOYENNE/FAIBLE remplissent les déficits restants
    #    en priorité sur les jours les plus chargés.
    # Cette approche évite que MALKI(12) reste inactif pendant que MAZZOUZ(2)
    # se retrouve surchargé à 7 sessions.

    # Nb de sessions actives max sur un seul jour pour un prof (Matin1, Matin2, Apm1, Apm2) = 4
    # Tous les profs avec charge_surv >= 4 seront considérés "forte charge" et dispos tous les jours.
    max_sessions_one_day = 4

    for p in sorted(prof_ids, key=lambda pp: -prof_data[pp]['charge_surv']):
        charge = prof_data[p]['charge_surv']
        if charge < 2:
            continue  # bloqué par CONTRAINTE 0

        mandatory_days = prof_data[p]['matieres_days']
        free_days = [d for d in range(1, 7)
                     if d not in mandatory_days and sessions_per_day.get(d, 0) > 0]

        # Heuristique d'origine pour limiter l'espace de recherche (évite le timeout du solveur)
        remaining_charge = max(0, charge - len(mandatory_days))
        if remaining_charge > 0:
            deficit_day = {}
            for d in free_days:
                need   = sessions_per_day.get(d, 0) * 2
                supply = sum(1 for pp in available_per_day[d] if prof_data[pp]['charge_surv'] >= 2)
                deficit_day[d] = max(0, need - supply)

            free_days_sorted = sorted(free_days, key=lambda d: -deficit_day[d])
            # On leur donne jusqu'à 6 choix de jours, mais on priorise les jours en déficit
            for d in free_days_sorted[:remaining_charge + 2]:
                available_per_day[d].add(p)
    # ÉTAPE 5 — DÉTECTION DÉFICIT ET EMPRUNT DU LENDEMAIN
    # ================================================================== #
    borrow_log    = {day: [] for day in range(1, 7)}
    bilan_par_jour = {}

    print("\n" + "="*60)
    print("  BILAN SESSIONS PAR JOUR + EMPRUNTS")
    print("="*60)

    for day in range(1, 7):
        day_name = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'][day-1]
        nb_sessions    = sessions_per_day.get(day, 0)
        profs_need     = nb_sessions * 2          # 2 profs par créneau
        profs_dispo    = len(available_per_day[day])
        deficit        = max(0, profs_need - profs_dispo)

        print(f"\n  {day_name} :")
        print(f"    Sessions actives   : {nb_sessions}")
        print(f"    Profs nécessaires  : {profs_need}")
        print(f"    Profs disponibles  : {profs_dispo}")
        print(f"    Déficit            : {deficit}")

        # Afficher la liste des salles et leurs sessions
        if active_slots.get(day):
            print(f"    Salles actives :")
            slot_names = {0:"Matin1", 1:"Matin2", 2:"AprèsMidi1", 3:"AprèsMidi2"}
            for room, slots in sorted(active_slots[day].items()):
                slot_str = ", ".join(slot_names[t] for t in slots)
                print(f"      {room}: [{slot_str}]")

        if deficit > 0:
            print(f"    -> Emprunt nécessaire depuis jour suivant...")
            borrow_sources = []
            if day > 1: borrow_sources.append(('hier', day - 1))
            if day < 6: borrow_sources.append(('demain', day + 1))
            
            for source_name, source_day in borrow_sources:
                if deficit <= 0: 
                    break
                
                candidates = []
                for p in available_per_day.get(source_day, set()):
                    if p in available_per_day[day]:
                        continue
                    
                    c_rest = charge_restante.get(p, 0)
                    # Règles du client:
                    # - Si depuis hier: charge restante >= 2
                    # - Si depuis demain: charge restante > 4
                    if source_name == 'hier' and c_rest >= 2:
                        candidates.append(p)
                    elif source_name == 'demain' and c_rest > 4:
                        candidates.append(p)
                
                # Tri : matière source en premier, puis charge restante desc
                candidates.sort(key=lambda p: (
                    -int(source_day in prof_data[p]['matieres_days']),
                    -charge_restante[p]
                ))

                for p in candidates:
                    if deficit <= 0:
                        break
                    available_per_day[day].add(p)
                    borrow_log[day].append(p)
                    deficit -= 1
                    print(f"      + Emprunté depuis {source_name} (jour {source_day}): "
                          f"{prof_data[p]['full_name']} "
                          f"(charge: {charge_restante[p]})")

            if deficit > 0:
                print(f"    /!\\ DÉFICIT RÉSIDUEL : {deficit} profs manquants !")

        bilan_par_jour[day] = {
            "sessions_actives":           nb_sessions,
            "profs_necessaires":          profs_need,
            "profs_disponibles_initial":  profs_dispo,
            "deficit_initial":            max(0, profs_need - profs_dispo),
            "profs_empruntes":            [prof_data[p]['full_name'] for p in borrow_log[day]],
            "profs_disponibles_final":    len(available_per_day[day])
        }

    # ================================================================== #
    # ÉTAPE 6 — MODÈLE CP-SAT
    # ================================================================== #
    model = cp_model.CpModel()

    x             = {}   # x[p,d,room,t]  : prof p en salle room slot t jour d
    y             = {}   # y[p,d,room]    : prof p présent salle room jour d
    used_day      = {}   # used_day[p,d]  : prof p surveille au moins 1 slot jour d
    assigned_slot = {}   # assigned_slot[p,d,t]
    is_start      = {}   # is_start[p,d,t]

    room_has_low  = {}
    room_has_high = {}
    reinforce     = {}

    for day in range(1, 7):
        for room in active_slots.get(day, {}).keys():
            room_has_low [(day, room)] = model.NewBoolVar(f"hasL_{day}_{room}")
            room_has_high[(day, room)] = model.NewBoolVar(f"hasH_{day}_{room}")
            reinforce    [(day, room)] = model.NewBoolVar(f"reinf_{day}_{room}")

    # Charge maximale globale → utilisée pour calculer la pénalité différentielle
    # Un prof avec charge 2 paiera beaucoup plus cher qu'un prof avec charge 10
    max_charge_global = max(
        (prof_data[p]['charge_surv'] for p in prof_ids if prof_data[p]['charge_surv'] > 0),
        default=1
    )

    objective_terms = []

    for day in range(1, 7):
        avail_today = available_per_day[day]

        for p in prof_ids:
            used_day[(p, day)] = model.NewBoolVar(f"ud_{p}_{day}")
            is_mandatory = (day in prof_data[p]['matieres_days'])
            charge_insuffisante = (prof_data[p]['charge_surv'] < 2)

            # ── CONTRAINTE 0 : CHARGE INSUFFISANTE → AFFECTATION INTERDITE (HARD)
            # Demande du client : "force limit if he have 1 you can not let him presete"
            if charge_insuffisante:
                model.Add(used_day[(p, day)] == 0)

            # ── CONTRAINTE 1 : PRÉSENCE OBLIGATOIRE (SOFT TRES FORTE)
            # Si un prof n'a pas assez de charge pour couvrir TOUS ses jours obligatoires,
            # on l'autorise à manquer un jour obligatoire avec pénalité, pour garder le paramètre max_charge inviolé.
            elif is_mandatory:
                missed_mandatory = model.NewBoolVar(f"miss_{p}_{day}")
                model.Add(used_day[(p, day)] + missed_mandatory == 1)
                objective_terms.append(1_000_000 * missed_mandatory)
            elif p not in avail_today:
                objective_terms.append(50_000 * used_day[(p, day)])

            for t in range(4):
                assigned_slot[(p, day, t)] = model.NewBoolVar(f"as_{p}_{day}_{t}")
                is_start     [(p, day, t)] = model.NewBoolVar(f"ist_{p}_{day}_{t}")

                room_assignments = []
                for room in active_slots.get(day, {}).keys():
                    if t in active_slots[day][room]:
                        key = (p, day, room, t)
                        if key not in x:
                            x[key] = model.NewBoolVar(f"x_{p}_{day}_{room}_{t}")
                            if (p, day, room) not in y:
                                y[(p, day, room)] = model.NewBoolVar(f"y_{p}_{day}_{room}")
                            model.Add(x[key] <= y[(p, day, room)])

                        room_assignments.append(x[key])

                if room_assignments:
                    model.Add(assigned_slot[(p, day, t)] == sum(room_assignments))
                else:
                    model.Add(assigned_slot[(p, day, t)] == 0)

                model.Add(used_day[(p, day)] >= assigned_slot[(p, day, t)])

                if t == 0:
                    model.Add(is_start[(p, day, t)] == assigned_slot[(p, day, t)])
                else:
                    model.Add(is_start[(p, day, t)] >= (
                        assigned_slot[(p, day, t)] - assigned_slot[(p, day, t-1)]))

            model.Add(used_day[(p, day)] <= sum(
                assigned_slot[(p, day, t)] for t in range(4)))

    # Liens y ↔ sessions + indicateurs low/high
    for day in range(1, 7):
        for room, slots_in_room in active_slots.get(day, {}).items():
            for p in prof_ids:
                if (p, day, room) not in y:
                    y[(p, day, room)] = model.NewBoolVar(f"y_{p}_{day}_{room}")

                session_vars_m = [x[(p, day, room, t)] for t in slots_in_room if t in (0, 1) and (p, day, room, t) in x]
                session_vars_a = [x[(p, day, room, t)] for t in slots_in_room if t in (2, 3) and (p, day, room, t) in x]

                ym = model.NewBoolVar(f"ym_{p}_{day}_{room}")
                ya = model.NewBoolVar(f"ya_{p}_{day}_{room}")

                # ── ALL-OR-NONE PAR DEMI-JOURNÉE ──
                # Un professeur affecté à une salle le matin doit faire TOUTES les sessions du matin (0 et 1).
                # S'il y est l'après-midi, il doit faire TOUTES les sessions de l'après-midi (2 et 3).
                # Cela permet à un prof avec peu de charge de faire juste le matin ou juste l'après-midi.
                if session_vars_m:
                    for sv in session_vars_m:
                        model.Add(sv == ym)
                else:
                    model.Add(ym == 0)

                if session_vars_a:
                    for sv in session_vars_a:
                        model.Add(sv == ya)
                else:
                    model.Add(ya == 0)

                model.AddMaxEquality(y[(p, day, room)], [ym, ya])

                c_val = prof_data[p]['charge_surv']
                if c_val <= 2:
                    model.Add(room_has_low [(day, room)] >= y[(p, day, room)])
                elif c_val >= 4:
                    model.Add(room_has_high[(day, room)] >= y[(p, day, room)])

            model.AddMultiplicationEquality(
                reinforce[(day, room)],
                [room_has_low[(day, room)], room_has_high[(day, room)]])

    # ================================================================== #
    # CONTRAINTE 4 — AFFINITÉ SALLE : au plus 2 salles par prof par jour
    # (Par exemple, Salle A le matin, Salle B l'après-midi).
    # Combiné avec le "All-Or-None par demi-journée", un professeur fera 
    # exactement la même salle pour tout le matin, et peut changer 
    # de salle pour tout l'après-midi. Cela débloque les profs à forte charge !
    # ================================================================== #
    for day in range(1, 7):
        for p in prof_ids:
            rooms_today = list(active_slots.get(day, {}).keys())
            y_day = [y[(p, day, r)] for r in rooms_today if (p, day, r) in y]
            if len(y_day) > 2:
                model.Add(sum(y_day) <= 2)

    # ================================================================== #
    # ÉTAPE 7 — OBJECTIFS
    # ================================================================== #

    # ── CONTRAINTE 2 : EXACTEMENT 2 PROFS PAR SESSION PAR SALLE (HARD)
    for day in range(1, 7):
        for room, slots_in_room in active_slots.get(day, {}).items():
            for t in slots_in_room:
                assigned_count = sum(
                    x[(p, day, room, t)]
                    for p in prof_ids if (p, day, room, t) in x)

                missing = model.NewIntVar(0, 4, f"miss_{day}_{room}_{t}")
                extra   = model.NewIntVar(0, 4, f"extr_{day}_{room}_{t}")

                model.Add(
                    assigned_count + missing - extra == 2)

                objective_terms.append(100_000_000 * missing)
                objective_terms.append( 50_000_000 * extra)

    # ── CONTRAINTE 3 : CHARGE EN SESSIONS (HARD STRICTE)
    # AUCUN dépassement n'est autorisé. Un professeur ne peut PAS dépasser sa limite.
    for p in prof_ids:
        all_sessions = [
            x[(p, day, room, t)]
            for day in range(1, 7)
            for room, slots in active_slots.get(day, {}).items()
            for t in slots
            if (p, day, room, t) in x
        ]
        if all_sessions:
            total_sessions_p = sum(all_sessions)
            max_charge       = prof_data[p]['charge_surv']

            if max_charge <= 0:
                # Charge nulle → aucune session autorisée
                model.Add(total_sessions_p == 0)
            else:
                # Dépassement rigoureusement interdit (HARD LIMIT)
                model.Add(total_sessions_p <= max_charge)

            # Bonus soft : utiliser au maximum la charge disponible (surtout pour les fortes charges)
            underuse = model.NewIntVar(0, 30, f"und_{p}")
            model.Add(total_sessions_p + underuse >= max(0, max_charge))
            objective_terms.append(1_000 * underuse)

    # ── SOFTS
    for p in prof_ids:
        for day in range(1, 7):
            # Changement de salle : maintenant garanti par CONTRAINTE 4
            # (sum(y_day) <= 1), donc sum(rel_y) <= 1 toujours.
            # Le terme précédent (sum(rel_y) - used_day) valait toujours 0.
            # On conserve uniquement la compacité et le coût de déplacement.
            rel_y = [y[(p, day, r)]
                     for r in active_slots.get(day, {}).keys()
                     if (p, day, r) in y]

            # Compacité des sessions (minimiser interruptions)
            objective_terms.append(5_000 * used_day[(p, day)])
            objective_terms.append(2_000 * (
                sum(is_start[(p, day, t)] for t in range(4)) - used_day[(p, day)]))

    for (p, day, room) in y:
        base_weight = 100 if day in prof_data[p]['matieres_days'] else 500
        # ── PRIORITÉ PAR CHARGE (SOFT) ──────────────────────────────────────
        # Pénalité différentielle : utiliser un prof à FAIBLE charge coûte
        # beaucoup plus cher qu'utiliser un prof à FORTE charge.
        # Exemple : max_charge=12, charge_ammar=6 → penalty = (12-6)*400 = 2400
        #           max_charge=12, charge_malek=10 → penalty = (12-10)*400 = 800
        # ⇒ Le solveur préférera MALEK (moins cher) à AMMAR pour chaque salle.
        charge_p = prof_data[p]['charge_surv']
        charge_priority_penalty = max(0, max_charge_global - charge_p) * 400
        objective_terms.append((base_weight + charge_priority_penalty) * y[(p, day, room)])

    model.Minimize(sum(objective_terms))
    print(f"\nObjective terms: {len(objective_terms)}")

    # ================================================================== #
    # ÉTAPE 8 — RÉSOLUTION
    # ================================================================== #
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120
    solver.parameters.log_search_progress = True
    solver.parameters.num_search_workers  = 16
    solver.parameters.symmetry_level      = 0

    print("\n--- DÉBUT RÉSOLUTION CP-SAT ---")
    status = solver.Solve(model)
    print(f"Statut : {solver.StatusName(status)}")

    # ================================================================== #
    # ÉTAPE 9 — EXTRACTION RÉSULTATS ET CALCUL CHARGE RESTANTE
    # ================================================================== #
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("ERROR: Aucune solution trouvée!")
        return False

    # ================================================================== #
    # POST-PROCESSING GLOUTON (REMPLISSAGE DES SESSIONS INCOMPLÈTES)
    # ================================================================== #
    assigned_val = {}
    for p in prof_ids:
        for day in range(1, 7):
            for room, slots in active_slots.get(day, {}).items():
                for t in slots:
                    if (p, day, room, t) in x:
                        assigned_val[(p, day, room, t)] = solver.Value(x[(p, day, room, t)])

    current_used = {p: sum(assigned_val[k] for k in assigned_val if k[0] == p and assigned_val[k] == 1) for p in prof_ids}

    print("\n--- POST-PROCESSING (REMPLISSAGE MANUEL DES TROUS) ---")
    for day in range(1, 7):
        if day not in active_slots: continue
        for room, slots_in_room in active_slots[day].items():
            for half_slots in ([0, 1], [2, 3]):
                h_slots = [t for t in half_slots if t in slots_in_room]
                if not h_slots: continue
                
                t_first = h_slots[0]
                profs_here = [p for p in prof_ids if assigned_val.get((p, day, room, t_first), 0) == 1]
                missing = 2 - len(profs_here)
                
                while missing > 0:
                    candidates = []
                    for p in prof_ids:
                        if p in profs_here: continue
                        if prof_data[p]['charge_surv'] - current_used[p] < len(h_slots): continue
                        
                        busy = False
                        for t in h_slots:
                            for r in active_slots[day].keys():
                                if assigned_val.get((p, day, r, t), 0) == 1:
                                    busy = True
                        if busy: continue
                        candidates.append(p)
                        
                    if not candidates:
                        break
                        
                    candidates.sort(key=lambda p: -(prof_data[p]['charge_surv'] - current_used[p]))
                    best_p = candidates[0]
                    
                    for t in h_slots:
                        assigned_val[(best_p, day, room, t)] = 1
                    current_used[best_p] += len(h_slots)
                    profs_here.append(best_p)
                    missing -= 1
                    print(f"    [PATCH GLOUTON] {prof_data[best_p]['full_name']} -> Salle {room} (Jour {day})")

    # Calcul des sessions réellement utilisées par prof
    prof_sessions_used = current_used

    # Calcul sessions par jour par prof (pour affichage progressive)
    prof_sessions_by_day = {p: {} for p in prof_ids}
    for p in prof_ids:
        cumul = 0
        for day in range(1, 7):
            sessions_today = sum(
                assigned_val.get((p, day, room, t), 0)
                for room, slots in active_slots.get(day, {}).items()
                for t in slots
            )
            cumul += sessions_today
            prof_sessions_by_day[p][day] = {
                'sessions_ce_jour':  sessions_today,
                'cumul':             cumul,
                'charge_restante':   max(0, prof_data[p]['charge_surv'] - cumul)
            }

    # ================================================================== #
    # ÉTAPE 10 — CONSTRUCTION JSON
    # ================================================================== #
    slot_names = {0:"Matin 1", 1:"Matin 2", 2:"Après-midi 1", 3:"Après-midi 2"}
    days_names = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi']

    room_list = sorted(list(set(r['salle_name'] for r in salle_filieres)))
    results_by_room = {
        room: {'salle': room, 'total_profs_week': set(),
               'daily': {}, 'building': room[0]}
        for room in room_list
    }

    print("\n" + "="*60)
    print("  RÉSULTATS PAR SALLE ET PAR JOUR")
    print("="*60)

    for day in range(1, 7):
        day_name = days_names[day-1]
        if day not in active_slots:
            continue

        print(f"\n  -- {day_name} --")

        for room, slots_in_room in sorted(active_slots[day].items()):
            if room not in results_by_room:
                continue

            print(f"\n    Salle {room}:")
            room_sessions          = {}
            daily_profs_for_stats  = []
            total_assignments_day  = 0

            for t in slots_in_room:
                s_name = slot_names[t]
                room_sessions[s_name] = []
                profs_in_slot = []

                for p in prof_ids:
                    if (p, day, room, t) in x and assigned_val.get((p, day, room, t), 0) == 1:
                        charge_tot   = prof_data[p]['charge_surv']
                        sessions_tot = prof_sessions_used[p]
                        # Charge restante APRÈS toute la semaine
                        charge_rest  = max(0, charge_tot - sessions_tot)
                        # Charge restante APRÈS ce jour (progressive)
                        charge_rest_apres_jour = prof_sessions_by_day[p][day]['charge_restante']

                        borrowed = p in borrow_log.get(day, [])

                        entry = {
                            "full_name":              prof_data[p]['full_name'],
                            "grade":                  prof_data[p]['grade'],
                            "charge_totale":          charge_tot,
                            "sessions_utilisees":     sessions_tot,
                            "charge_restante":        charge_rest,
                            "charge_restante_apres_ce_jour": charge_rest_apres_jour,
                            "sessions_ce_jour":       prof_sessions_by_day[p][day]['sessions_ce_jour'],
                            "jours_matiere":          sorted(list(prof_data[p]['matieres_days'])),
                            "emprunte_depuis_lendemain": borrowed,
                            # Affichage clair : X/Total (reste Y)
                            "affichage_charge":       (
                                f"{sessions_tot}/{charge_tot} sessions "
                                f"(reste: {charge_rest}) "
                                f"{'[EMPRUNTÉ]' if borrowed else ''}"
                            ),
                            "charge": f"{sessions_tot}/{charge_tot}"
                        }
                        room_sessions[s_name].append(entry)
                        profs_in_slot.append(prof_data[p]['full_name'])
                        daily_profs_for_stats.append(p)
                        total_assignments_day += 1

                # Affichage console pour ce slot
                target = 2
                nb_assigned = len(profs_in_slot)
                status_icon = "OK" if nb_assigned >= target else f"ERR(manque {target-nb_assigned})"
                print(f"      {s_name}: {nb_assigned}/{target} profs {status_icon} "
                      f"-> {', '.join(profs_in_slot) if profs_in_slot else 'VIDE'}")

            if total_assignments_day > 0:
                results_by_room[room]['daily'][day_name] = {
                    'sessions':       room_sessions,
                    'profs_count':    len(set(daily_profs_for_stats)),
                    'profs_needed':   total_assignments_day,
                    'target_surv':    2,
                    'matin_sessions': sum(1 for t in slots_in_room if t < 2),
                    'apmidi_sessions':sum(1 for t in slots_in_room if t >= 2),
                    'bilan': {
                        'slots_actifs':    len(slots_in_room),
                        'slots_remplis':   sum(
                            1 for t in slots_in_room
                            if sum(assigned_val.get((p, day, room, t), 0)
                                   for p in prof_ids
                                   if (p, day, room, t) in x) >= 2
                        )
                    }
                }
                results_by_room[room]['total_profs_week'].update(daily_profs_for_stats)

    # ── CHARGE SUMMARY : résumé visuel de tous les profs
    charge_summary = []
    print("\n" + "="*60)
    print("  RÉSUMÉ CHARGE DE TOUS LES PROFS")
    print("="*60)
    print(f"  {'Nom':<30} {'Grade':<10} {'Charge':>7} {'Utilisé':>8} {'Reste':>6} {'Statut'}")
    print("  " + "-"*70)

    for p in prof_ids:
        charge_tot  = prof_data[p]['charge_surv']
        sess_used   = prof_sessions_used[p]
        reste       = max(0, charge_tot - sess_used)
        statut      = "OK" if sess_used <= charge_tot else "/!\\ DÉPASSEMENT"
        # Détail jour par jour
        detail_jours = []
        for day in range(1, 7):
            d_info = prof_sessions_by_day[p][day]
            if d_info['sessions_ce_jour'] > 0:
                detail_jours.append(
                    f"{days_names[day-1][:3]}:{d_info['sessions_ce_jour']}sess"
                    f"(reste:{d_info['charge_restante']})")

        print(f"  {prof_data[p]['full_name']:<30} "
              f"{str(prof_data[p]['grade']):<10} "
              f"{charge_tot:>7} "
              f"{sess_used:>8} "
              f"{reste:>6}  "
              f"{statut}")
        if detail_jours:
            print(f"    |- {' | '.join(detail_jours)}")

        charge_summary.append({
            "nom":                prof_data[p]['full_name'],
            "grade":              prof_data[p]['grade'],
            "charge_totale":      charge_tot,
            "sessions_utilisees": sess_used,
            "charge_restante":    reste,
            "statut":             "OK" if sess_used <= charge_tot else "DÉPASSEMENT",
            "detail_par_jour":    {
                days_names[day-1]: {
                    "sessions":       prof_sessions_by_day[p][day]['sessions_ce_jour'],
                    "cumul":          prof_sessions_by_day[p][day]['cumul'],
                    "charge_restante":prof_sessions_by_day[p][day]['charge_restante']
                }
                for day in range(1, 7)
                if prof_sessions_by_day[p][day]['sessions_ce_jour'] > 0
            },
            "jours_matiere":     sorted(list(prof_data[p]['matieres_days'])),
            "emprunts":          [
                days_names[day-1]
                for day in range(1, 7)
                if p in borrow_log.get(day, [])
            ],
            "affichage":  f"{sess_used}/{charge_tot} (reste: {reste})"
        })

    # ── FINALISER JSON
    final_results = []
    for room, data in results_by_room.items():
        data['total_profs'] = len(data['total_profs_week'])
        del data['total_profs_week']
        if data['daily']:
            final_results.append(data)
    final_results.sort(key=lambda item: (item['building'], item['salle']))

    # Bilan jours formaté
    bilan_jours_json = {
        days_names[d-1]: {
            "bilan_jour": bilan_par_jour[d]
        }
        for d in range(1, 7)
    }

    output = {
        'status':         'success',
        'solve_time':     round(time.time() - t_start, 2),
        'source':         'ortools',
        'data':           final_results,
        'bilan_jours':    bilan_jours_json,
        'charge_summary': charge_summary,
        'borrow_log':     {
            days_names[d-1]: [prof_data[p]['full_name'] for p in ps]
            for d, ps in borrow_log.items() if ps
        }
    }

    with open('surveillance_cache.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # -- RÉSUMÉ FINAL CONSOLE
    total_slots  = sum(sessions_per_day[d] for d in range(1, 7))
    filled_slots = sum(
        1
        for day in range(1, 7)
        for room, slots in active_slots.get(day, {}).items()
        for t in slots
        if sum(solver.Value(x[(p, day, room, t)])
               for p in prof_ids
               if (p, day, room, t) in x) >= 2
    )

    print(f"\n{'='*60}")
    print(f"  RÉSUMÉ FINAL")
    print(f"{'='*60}")
    print(f"  Créneaux remplis (>=2 profs) : {filled_slots} / {total_slots}")
    print(f"  Profs avec dépassement       : "
          f"{sum(1 for c in charge_summary if c['statut'] == 'DÉPASSEMENT')}")
    print(f"  Temps de résolution          : {round(time.time()-t_start,2)}s")
    print(f"  Solution sauvegardée         : surveillance_cache.json")
    print(f"{'='*60}\n")

    return True


if __name__ == '__main__':
    generate_surveillance()