import json
with open('surveillance_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
print(f'Total rooms: {len(d["data"])}')
missing_slots = 0
for r in d["data"]:
    for day, day_data in r["daily"].items():
        for slot, profs in day_data["sessions"].items():
            if len(profs) < 2:
                missing_slots += 1
print(f'Missing < 2 slots: {missing_slots}')
