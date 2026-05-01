import json

with open('surveillance_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

profs = d['charge_summary']
total_charge = sum(p['charge_totale'] for p in profs)
total_used   = sum(p['sessions_utilisees'] for p in profs)

over = [(p['nom'], p['charge_totale'], p['sessions_utilisees'])
        for p in profs if p['sessions_utilisees'] > p['charge_totale']]
over.sort(key=lambda x: -(x[2] - x[1]))

print(f"Sessions utilisees  : {total_used} / {total_charge}")
print(f"Profs avec depassement : {len(over)}")
print()
if over:
    print(f"  {'Nom':<32} {'Charge':<8} {'Utilise':<9} Excess")
    for nom, charge, use in over[:10]:
        print(f"  {nom:<32} {charge:<8} {use:<9} +{use - charge}")
