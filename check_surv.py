import mysql.connector
import os

def test_algo():
    conn = mysql.connector.connect(host=os.getenv('DB_HOST', '127.0.0.1'), user=os.getenv('DB_USER', 'root'), password='', database='gestion_examens_s1')
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id_professeur as id, nom_prenom as full_name, grade, charge_surv FROM professeur")
    profs_db = cursor.fetchall()
    
    cursor.execute("SELECT id_matiere, nom_matiere, jour_num, id_professeur, has_examen FROM matiere WHERE has_examen=1 AND jour_num IS NOT NULL")
    matieres = cursor.fetchall()
    
    cursor.execute("SELECT salle_name, type_session, id_filiere1, id_filiere2 FROM salle_filieres")
    salle_filieres = cursor.fetchall()
    
    cursor.execute("SELECT id_filaire, jour_num, COUNT(*) as exam_count FROM matiere WHERE has_examen = 1 AND jour_num IS NOT NULL GROUP BY id_filaire, jour_num")
    exam_data = cursor.fetchall()

    filiere_counts = {}
    for row in exam_data:
        fid = row['id_filaire']
        jno = row['jour_num']
        if fid not in filiere_counts: filiere_counts[fid] = {}
        filiere_counts[fid][jno] = row['exam_count']

    prof_state = {}
    for p in profs_db:
        if p['charge_surv'] is None: p['charge_surv'] = 0
        prof_state[p['id']] = {
            'full_name': p['full_name'],
            'grade': p['grade'],
            'total_charges': p['charge_surv'],
            'reste_charges': p['charge_surv'],
            'jours_obligatoires': set()
        }

    for m in matieres:
        pid = m['id_professeur']
        if pid in prof_state and m['jour_num']:
            prof_state[pid]['jours_obligatoires'].add(m['jour_num'])

    available_pool = []
    global_pool = [p['id'] for p in profs_db]
    
    all_rooms = list(set(r['salle_name'] for r in salle_filieres))
    results_by_room = {room: {'salle': room, 'total_profs_set': set(), 'daily': {}, 'building': room[0]} for room in all_rooms}

    for day in range(1, 7):
        day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'][day-1]
        
        active_rooms = []
        for r in salle_filieres:
            c1 = filiere_counts.get(r['id_filiere1'], {}).get(day, 0) if r['id_filiere1'] else 0
            c2 = filiere_counts.get(r['id_filiere2'], {}).get(day, 0) if r['id_filiere2'] else 0
            if c1 > 0 or c2 > 0:
                if r['salle_name'] not in active_rooms:
                    active_rooms.append(r['salle_name'])
                    
        profs_of_day = [pid for pid in prof_state if day in prof_state[pid]['jours_obligatoires'] and prof_state[pid]['reste_charges'] > 0]
        
        for room in active_rooms:
            sessions_needed = 8 # 4 sessions * 2 profs per session
            room_assigned_profs = {}
            
            while sessions_needed > 0:
                assigned_prof = None
                
                for pid in room_assigned_profs:
                    if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs[pid] < 4:
                        assigned_prof = pid
                        break
                
                if not assigned_prof:
                    for pid in profs_of_day:
                        if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs.get(pid, 0) < 4:
                            assigned_prof = pid
                            break
                            
                if not assigned_prof:
                    for pid in available_pool:
                        if prof_state[pid]['reste_charges'] > 0 and room_assigned_profs.get(pid, 0) < 4:
                            assigned_prof = pid
                            break
                            
                if not assigned_prof:
                    for pid in global_pool:
                        if prof_state[pid]['reste_charges'] > 0 and pid not in available_pool and room_assigned_profs.get(pid, 0) < 4:
                            assigned_prof = pid
                            available_pool.append(pid)
                            break
                
                if assigned_prof:
                    prof_state[assigned_prof]['reste_charges'] -= 1
                    sessions_needed -= 1
                    room_assigned_profs[assigned_prof] = room_assigned_profs.get(assigned_prof, 0) + 1
                    results_by_room[room]['total_profs_set'].add(assigned_prof)
                else:
                    break
                    
            results_by_room[room]['daily'][day_name] = {
               'matin_sessions': 2,
               'apmidi_sessions': 2,
               'profs_needed': sum(room_assigned_profs.values()),
               'profs': [
                   {
                       'full_name': prof_state[pid]['full_name'],
                       'grade': prof_state[pid]['grade'],
                       'charge': f"{count} sess. (Rest: {prof_state[pid]['reste_charges']})"
                   }
                   for pid, count in room_assigned_profs.items()
               ]
            }

        for pid in profs_of_day:
            if prof_state[pid]['reste_charges'] > 0 and pid not in available_pool:
                available_pool.append(pid)

    final_results = []
    for room, data in results_by_room.items():
        data['total_profs'] = len(data['total_profs_set'])
        del data['total_profs_set']
        if len(data['daily']) > 0:
            final_results.append(data)
            
    final_results.sort(key=lambda x: (x['building'], x['salle']))
    print(f"Total rooms processed: {len(final_results)}")
    if final_results:
        print(f"Example K01: {final_results[0]}")

if __name__ == '__main__':
    test_algo()
