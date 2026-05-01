import json
with open('surveillance_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

profs = {}
for r in d["data"]:
    room = r["salle"]
    for day, day_data in r["daily"].items():
        for slot, slot_profs in day_data["sessions"].items():
            for p in slot_profs:
                name = p["full_name"]
                if name not in profs: profs[name] = []
                profs[name].append((day, room, slot))

# Check MAZZOUZ Souha
print(f'MAZZOUZ Souha: {profs.get("MAZZOUZ Souha", [])}')

# Total counts
print(f'Total rooms: {len(d["data"])}')
total_slots = 0
empty_slots = 0
for r in d["data"]:
    for day, day_data in r["daily"].items():
        for slot, slot_profs in day_data["sessions"].items():
            total_slots += 1
            if not slot_profs:
                empty_slots += 1

print(f'Total sessions: {total_slots}')
print(f'Empty sessions: {empty_slots}')
