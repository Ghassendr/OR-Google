import json
from ortools.sat.python import cp_model

# ==========================================
# 1. CHARGEMENT DES FICHIERS JSON
# ==========================================

def load_data():
    try:
        with open('class.json', 'r', encoding='utf-8') as f:
            rooms_data = json.load(f)
        
        with open('filier.json', 'r', encoding='utf-8') as f:
            filieres_data = json.load(f)
            
        return rooms_data, filieres_data
    except FileNotFoundError as e:
        print(f"Erreur : Le fichier n'a pas été trouvé ({e}). Vérifiez qu'ils sont dans le dossier.")
        exit()

rooms_data, filieres_data_raw = load_data()

# ==========================================
# 2. PRÉPARATION DES DONNÉES
# ==========================================

# Configuration
BUFFER = 4  # Places vides obligatoires par salle
# On trie les salles par capacité décroissante (Stratégie: Grandes salles d'abord)
rooms_data.sort(key=lambda x: x['CapaciteTotal'], reverse=True)

# Calcul de la capacité maximale utilisable (la plus grande salle - buffer)
MAX_ROOM_CAPACITY = max(r['CapaciteTotal'] for r in rooms_data)
SAFE_MAX_CAP = MAX_ROOM_CAPACITY - BUFFER 

groups = []
group_id_counter = 0

def create_groups(filiere_name, count, category):
    """Découpe une grande filière en sous-groupes qui rentrent dans les salles."""
    global group_id_counter
    remaining = count
    part = 1
    
    while remaining > 0:
        # On crée un groupe de la taille max possible (SAFE_MAX_CAP) ou le reste
        size = min(remaining, SAFE_MAX_CAP)
        
        groups.append({
            'id': group_id_counter,
            'name': f"{filiere_name}_G{part}", # Nom unique (ex: L_EEA_G1)
            'type': filiere_name,              # Type original pour la contrainte "Max 2 types"
            'category': category,              # Ex: 1ere_annee
            'size': size
        })
        
        remaining -= size
        part += 1
        group_id_counter += 1

# Parcours du JSON complexe (Années -> Filières/Programmes)
print("Traitement des filières...")
if 'annees' in filieres_data_raw:
    for niveau, data in filieres_data_raw['annees'].items():
        # Gestion des cas "filieres" (Licence/Prépa) et "programmes" (Master)
        sub_dict = data.get('filieres') or data.get('programmes')
        
        if sub_dict:
            for nom_filiere, nombre_etudiants in sub_dict.items():
                create_groups(nom_filiere, nombre_etudiants, niveau)

print(f"Total Salles disponibles : {len(rooms_data)}")
print(f"Total Groupes à placer : {len(groups)}")

# ==========================================
# 3. MODÉLISATION OR-TOOLS
# ==========================================

model = cp_model.CpModel()

# --- Variables ---
# x[(groupe_id, salle_idx)] : booléen, le groupe est-il dans cette salle ?
x = {}
for g in groups:
    for r_idx, r in enumerate(rooms_data):
        x[(g['id'], r_idx)] = model.NewBoolVar(f"x_{g['id']}_{r_idx}")

# type_present[(type_filiere, salle_idx)] : booléen, ce type de filière est-il dans la salle ?
unique_types = list(set(g['type'] for g in groups))
type_present = {}
for t in unique_types:
    for r_idx, r in enumerate(rooms_data):
        type_present[(t, r_idx)] = model.NewBoolVar(f"type_{t}_{r_idx}")

# --- Contraintes ---

# C1. Chaque groupe doit être assigné à une seule salle
for g in groups:
    model.Add(sum(x[(g['id'], r_idx)] for r_idx in range(len(rooms_data))) == 1)

# C2. Capacité des salles (avec Buffer de 4 places vides)
for r_idx, r in enumerate(rooms_data):
    salle_cap = r['CapaciteTotal']
    # Somme des étudiants dans la salle <= Capacité - 4
    model.Add(
        sum(x[(g['id'], r_idx)] * g['size'] for g in groups) <= (salle_cap - BUFFER)
    )

# C3. Liaison : Si un groupe est dans une salle, son "Type" est marqué présent
for r_idx in range(len(rooms_data)):
    for t in unique_types:
        groups_of_this_type = [g for g in groups if g['type'] == t]
        vars_in_room = [x[(g['id'], r_idx)] for g in groups_of_this_type]
        
        if vars_in_room:
            # Si au moins un groupe de ce type est présent, type_present = 1
            model.AddMaxEquality(type_present[(t, r_idx)], vars_in_room)
        else:
            model.Add(type_present[(t, r_idx)] == 0)

# C4. Mélange : Maximum 2 types de filières différents par salle
for r_idx in range(len(rooms_data)):
    model.Add(sum(type_present[(t, r_idx)] for t in unique_types) <= 2)

# --- Objectif ---
# Maximiser l'occupation intelligente : (Taille Groupe * Capacité Salle)
# Cela force les gros groupes vers les grosses salles
objective_terms = []
for g in groups:
    for r_idx, r in enumerate(rooms_data):
        weight = g['size'] * r['CapaciteTotal']
        objective_terms.append(x[(g['id'], r_idx)] * weight)

model.Maximize(sum(objective_terms))

# ==========================================
# 4. RÉSOLUTION ET AFFICHAGE
# ==========================================
print("\nRecherche de la solution optimale...\n")
solver = cp_model.CpSolver()
# Optionnel : définir une limite de temps si c'est trop long
# solver.parameters.max_time_in_seconds = 30.0 

status = solver.Solve(model)

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print(f"Solution trouvée ! (Status: {solver.StatusName(status)})")
    print("-" * 60)
    
    # Organisation de l'affichage
    schedule = {r['Salle']: {'groups': [], 'total': 0, 'cap': r['CapaciteTotal']} for r in rooms_data}
    
    for r_idx, r in enumerate(rooms_data):
        for g in groups:
            if solver.Value(x[(g['id'], r_idx)]) == 1:
                schedule[r['Salle']]['groups'].append(g)
                schedule[r['Salle']]['total'] += g['size']

    # Affichage propre
    for salle_nom, data in schedule.items():
        if data['total'] > 0:
            libre = data['cap'] - data['total']
            types_in_room = set(g['type'] for g in data['groups'])
            
            print(f"SALLE {salle_nom} [Cap: {data['cap']} | Occupé: {data['total']} | Libre: {libre}]")
            print(f"  > Filières ({len(types_in_room)} types): {', '.join(types_in_room)}")
            for g in data['groups']:
                print(f"    - {g['name']} : {g['size']} étudiants ({g['category']})")
            print("-" * 30)
            
else:
    print("Aucune solution trouvée. Essayez de réduire le 'BUFFER' ou d'ajouter des salles.")