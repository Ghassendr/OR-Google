import urllib.request
import json
import sys

try:
    print("Fetching timeline details")
    req = urllib.request.urlopen("http://127.0.0.1:5000/api/timetable")
    timetable = json.loads(req.read())['timetable']

    req2 = urllib.request.urlopen("http://127.0.0.1:5000/api/matieres")
    matieres = json.loads(req2.read())['matieres']
    
    print(f"Total slots: {len(timetable)}")
    
    # Filter for Ingenieur A1
    fil_mat = [m for m in matieres if "Ingenieur A1" in m.get('filiere', '')]
    if fil_mat:
        fil_id = fil_mat[0]['filiere_id']
        t_slots = [t for t in timetable if t['filiere_id'] == fil_id]
        print(f"Slots for Ingenieur A1 (ID: {fil_id}): {len(t_slots)}")
        
        if len(t_slots) > 0:
            sample_slot = t_slots[0]
            m_id = sample_slot['matiere_id']
            m = next((m for m in matieres if m['id'] == m_id), None)
            print("Sample Slot:", sample_slot)
            print("Corresponding Matiere:", m)
            
            # Print DS/Examen flags for all subjects in this filiere
            print("\nDS/Examen distribution:")
            ds_count = sum(1 for m in fil_mat if str(m.get('ds')) in ('1', 'True', True))
            exam_count = sum(1 for m in fil_mat if str(m.get('examen')) in ('1', 'True', True))
            print(f"Total matieres: {len(fil_mat)}, DS: {ds_count}, Examen: {exam_count}")
    else:
        print("Filiere not found")

except Exception as e:
    print(e)
