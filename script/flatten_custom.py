import json
import csv
import os
from pathlib import Path

def fix_encoding(text):
    if not text:
        return ""
    # Common XML/UTF-8 double encoding issues in Italian documents
    replacements = {
        'Ã\xa0': 'à', 'Ã¨': 'è', 'Ã©': 'é', 'Ã¬': 'ì', 'Ã²': 'ò', 'Ã¹': 'ù',
        'Ã\xa0': 'à', 'Ã ': 'À', 'Ãˆ': 'È', 'Ã‰': 'É', 'ÃŒ': 'Ì', 'Ã’': 'Ò', 'Ã™': 'Ù',
        'â\x80\x93': '-', 'â\x80\x94': '-', 'â\x80\x9c': '"', 'â\x80\x9d': '"',
        'â\x80\x98': "'", 'â\x80\x99': "'", 'â\x80¦': '...', 'â\x82¬': '€',
        'Â«': '«', 'Â»': '»', 'â€‰': ' ', 'â€¯': ' ', 'Ã¯': 'ï'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Clean up multiple spaces and newlines
    text = " ".join(text.split())
    return text

def extract_article_num(target_info):
    if not target_info:
        return None
    # Usually "Emendamento n. 3.1" or "3.1"
    parts = target_info.replace("Emendamento n.", "").strip().split('.')
    if parts:
        return parts[0]
    return None

def flatten_atto(json_path, output_dir):
    print(f"Flattening {json_path} to CSV files in {output_dir}...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    atto_id = data.get('atto_id')
    leg = data.get('leg')

    # 1. Table: ATTI
    atti_headers = ['atto_id', 'legislatura']
    atti_row = {'atto_id': atto_id, 'legislatura': leg}
    
    # 2. Table: FIRMATARI ATTO
    firmatari_headers = ['atto_id', 'nome', 'genere', 'primo_firmatario']
    firmatari_rows = [
        {
            'atto_id': atto_id,
            'nome': f.get('nome'),
            'genere': f.get('genere'),
            'primo_firmatario': f.get('primo_firmatario')
        }
        for f in data.get('firmatari_atto', [])
    ]

    # 3. Table: ARTICOLI
    articoli_headers = ['atto_id', 'articolo_id', 'numero_articolo', 'titolo', 'versione', 'testo_integrale']
    articoli_rows = []
    
    for v_name, v_data in data.get('ddl_versions', {}).items():
        if v_data:
            for art in v_data.get('articles', []):
                paragraphs = art.get('paragraphs', [])
                full_text = "\n".join([p.get('text', '') for p in paragraphs])
                
                articoli_rows.append({
                    'atto_id': atto_id,
                    'articolo_id': art.get('id'),
                    'numero_articolo': art.get('num'),
                    'titolo': fix_encoding(art.get('heading')),
                    'versione': v_name,
                    'testo_integrale': fix_encoding(full_text)
                })

    # 4. Table: EMENDAMENTI (one row per amendment)
    emend_headers = [
        'atto_id', 'emendamento_id', 'numero_emendamento', 'articolo_target',
        'data', 'target_info', 'testo_emendamento'
    ]
    # 5. Table: PROPONENTI (one row per amendment × proponent)
    prop_headers = [
        'emendamento_id', 'proponente_id', 'proponente_nome',
        'proponente_gruppo', 'proponente_genere'
    ]
    emend_rows = []
    prop_rows = []
    seen_emend = set()

    for em in data.get('amendments', []):
        metadata = em.get('metadata', {})
        em_id = metadata.get('id')
        em_num = metadata.get('number')
        em_date = metadata.get('date')
        target = em.get('target_info')
        art_target = extract_article_num(em_num if em_num else target)
        em_text = "\n".join(em.get('content', []))

        if em_id not in seen_emend:
            emend_rows.append({
                'atto_id': atto_id,
                'emendamento_id': em_id,
                'numero_emendamento': em_num,
                'articolo_target': art_target,
                'data': em_date,
                'target_info': target,
                'testo_emendamento': fix_encoding(em_text)
            })
            seen_emend.add(em_id)

        for p in em.get('enriched_proponents', []):
            prop_rows.append({
                'emendamento_id': em_id,
                'proponente_id': p.get('id'),
                'proponente_nome': p.get('name'),
                'proponente_gruppo': p.get('group'),
                'proponente_genere': p.get('gender')
            })

    # Write CSVs
    write_csv(output_dir / "t_atti.csv", atti_headers, [atti_row])
    write_csv(output_dir / "t_firmatari_atto.csv", firmatari_headers, firmatari_rows)
    write_csv(output_dir / "t_articoli.csv", articoli_headers, articoli_rows)
    write_csv(output_dir / "t_emendamenti.csv", emend_headers, emend_rows)
    write_csv(output_dir / "t_proponenti.csv", prop_headers, prop_rows)
    
    print(f"Done! Files generated in {output_dir}")

def write_csv(path, headers, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to the consolidated JSON file")
    parser.add_argument("--out", default="data/Leg19/Atto00055193/flattened_custom", help="Output directory")
    args = parser.parse_args()
    
    if os.path.exists(args.file):
        flatten_atto(args.file, args.out)
    else:
        print(f"Error: {args.file} not found.")
