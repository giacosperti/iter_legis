import json
import csv
from pathlib import Path

def flatten_anagrafica(json_path, csv_path):
    print(f"Flattening {json_path} to {csv_path}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    senatori = data.get('senatori', [])
    
    # Define headers
    headers = [
        'senatore_id', 
        'full_name', 
        'first_name', 
        'last_name', 
        'gender', 
        'birth_date', 
        'gruppo_nome', 
        'gruppo_inizio', 
        'gruppo_fine',
        'gruppo_uri'
    ]
    
    rows = []
    for sen in senatori:
        base_info = {
            'senatore_id': sen.get('id'),
            'full_name': sen.get('full_name'),
            'first_name': sen.get('first_name'),
            'last_name': sen.get('last_name'),
            'gender': sen.get('gender'),
            'birth_date': sen.get('birth_date')
        }
        
        gruppi = sen.get('gruppi', [])
        if not gruppi:
            # Add a row anyway with empty group info
            row = base_info.copy()
            row.update({
                'gruppo_nome': None,
                'gruppo_inizio': None,
                'gruppo_fine': None,
                'gruppo_uri': None
            })
            rows.append(row)
        else:
            for grp in gruppi:
                row = base_info.copy()
                row.update({
                    'gruppo_nome': grp.get('nome'),
                    'gruppo_inizio': grp.get('inizio'),
                    'gruppo_fine': grp.get('fine'),
                    'gruppo_uri': grp.get('uri')
                })
                rows.append(row)
    
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Flattening complete. {len(rows)} rows generated.")

if __name__ == "__main__":
    input_file = Path("data/Leg19/Anagrafica/senatori_19.json")
    output_file = Path("data/Leg19/Anagrafica/senatori_19_flattened.csv")
    
    if input_file.exists():
        flatten_anagrafica(input_file, output_file)
    else:
        print(f"Error: {input_file} not found.")
