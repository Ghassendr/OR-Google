import json
import math
from ortools.sat.python import cp_model

# ==========================================
# 1. CHARGEMENT DES DONNÉES
# ==========================================

def load_data():
    with open('class.json', 'r', encoding='utf-8') as f:
        rooms = json.load(f)
    with open('filier.json', 'r', encoding='utf-8') as f:
        filieres = json.load(f)
    return rooms, filieres

rooms_data, raw_data = load_data()

BUFFER = 4
rooms_data.sort(key=lambda x: x['CapaciteTotal'], reverse=True)

MAX_CAPACITY = max(r['CapaciteTotal'] for r in rooms_data) - BUFFER

groups_matin = []
groups_apres_midi = []
group_id_counter = 0


# ==========================================
# 2. DÉCOUPAGE OBLIGATOIRE DES FILIÈRES
# ==========================================

def split_into_groups(name, count, category, session_list):
    global group_id_counter

    # Taille cible raisonnable (peut être ajustée)
    TARGET_SIZE = min(30, MAX_CAPACITY)

    # Toujours au moins 2 groupes
    num_groups = max(2, math.ceil(count / TARGET_SIZE))

    # Répartition équilibrée
    base_size = count // num_groups
    remainder = count % num_groups

    for i in range(num_groups):
        size = base_size + (1 if i < remainder else 0)

        session_list.append({
            'id': group_id_counter,
            'name': f"{name}_G{i+1}",
            'type': name,
            'size': size,
            'category': category
        })

        group_id_counter += 1


# ==========================================
# 3. SÉPARATION DES SESSIONS
# ==========================================

for niveau, data in raw_data['annees'].items():
    sub_dict = data.get('filieres') or data.get('programmes')
    if not sub_dict:
        continue

    for nom, effectif in sub_dict.items():

        if "Ingenieur" in nom or "Cycle_Preparatoire" in nom or niveau == "master":
            split_into_groups(nom, effectif, niveau, groups_matin)
        else:
            split_into_groups(nom, effectif, niveau, groups_apres_midi)


# ==========================================
# 4. MODÈLE OR-TOOLS
# ==========================================
def solve_session(session_name, groups, rooms):

    if not groups:
        print(f"\nAucun groupe pour {session_name}")
        return

    model = cp_model.CpModel()

    # Variables d'affectation
    x = {}
    for g in groups:
        for r_idx, r in enumerate(rooms):
            x[(g['id'], r_idx)] = model.NewBoolVar(f"x_{g['id']}_{r_idx}")

    unique_types = list(set(g['type'] for g in groups))
    type_present = {}

    for t in unique_types:
        for r_idx in range(len(rooms)):
            type_present[(t, r_idx)] = model.NewBoolVar(f"tp_{t}_{r_idx}")

    # Contraintes
    for g in groups:
        model.Add(sum(x[(g['id'], r_idx)] for r_idx in range(len(rooms))) == 1)

    for r_idx, r in enumerate(rooms):
        model.Add(
            sum(x[(g['id'], r_idx)] * g['size'] for g in groups)
            <= (r['CapaciteTotal'] - BUFFER)
        )

        for t in unique_types:
            g_of_type = [g for g in groups if g['type'] == t]
            vars_in_room = [x[(g['id'], r_idx)] for g in g_of_type]

            if vars_in_room:
                model.AddMaxEquality(type_present[(t, r_idx)], vars_in_room)
            else:
                model.Add(type_present[(t, r_idx)] == 0)

        model.Add(sum(type_present[(t, r_idx)] for t in unique_types) <= 2)

    # Objectif
    model.Maximize(
        sum(
            x[(g['id'], r_idx)] * g['size'] * r['CapaciteTotal']
            for g in groups
            for r_idx, r in enumerate(rooms)
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    status = solver.Solve(model)

    print("\n" + "=" * 70)
    print(f"SESSION : {session_name.upper()}")
    print("=" * 70)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("Aucune solution trouvée.")
        return

    total_students = 0
    total_capacity_used = 0

    room_results = []

    for r_idx, r in enumerate(rooms):

        assigned = [
            g for g in groups
            if solver.Value(x[(g['id'], r_idx)]) == 1
        ]

        if assigned:
            total = sum(g['size'] for g in assigned)
            capacity = r['CapaciteTotal'] - BUFFER
            occupancy = (total / capacity) * 100
            wasted = capacity - total

            room_results.append({
                "room": r['Salle'],
                "capacity": capacity,
                "total": total,
                "occupancy": occupancy,
                "wasted": wasted,
                "groups": assigned
            })

            total_students += total
            total_capacity_used += capacity

    # Trier par taux de remplissage décroissant
    room_results.sort(key=lambda x: x['occupancy'], reverse=True)

    # Affichage détaillé
    for room in room_results:
        print(f"\nSalle : {room['room']}")
        print(f"  Occupation : {room['total']} / {room['capacity']} "
              f"({room['occupancy']:.1f}%)")
        print(f"  Places inutilisées : {room['wasted']}")

        print("  Groupes :")
        for g in room['groups']:
            print(f"    - {g['name']} ({g['size']} étudiants)")

    # Statistiques globales
    global_occupancy = (total_students / total_capacity_used) * 100

    print("\n" + "-" * 70)
    print("STATISTIQUES GLOBALES")
    print("-" * 70)
    print(f"Total étudiants placés : {total_students}")
    print(f"Capacité totale utilisée : {total_capacity_used}")
    print(f"Taux global d’occupation : {global_occupancy:.2f}%")
    print("=" * 70)


# ==========================================
# 5. EXÉCUTION
# ==========================================

print(f"Effectif Matin : {sum(g['size'] for g in groups_matin)} étudiants")
print(f"Effectif Après-midi : {sum(g['size'] for g in groups_apres_midi)} étudiants")

solve_session("Matin (Ingénieurs + Prépa + Masters)", groups_matin, rooms_data)
solve_session("Après-midi (Licences)", groups_apres_midi, rooms_data)
