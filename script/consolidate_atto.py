import json
import os
import argparse
from pathlib import Path

def load_json(path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_proponent_info(sen_id, anagrafica, date_str):
    # Find senator in anagrafica
    sen_data = next((s for s in anagrafica['senatori'] if s['id'] == sen_id), None)
    if not sen_data:
        return {"id": sen_id, "error": "Senator not found"}
    
    # Find active group at date_str
    active_group = "Misto / Sconosciuto"
    if date_str:
        for grp in sen_data.get('gruppi', []):
            start = grp.get('inizio')
            end = grp.get('fine')
            if start and start <= date_str:
                if not end or end >= date_str:
                    active_group = grp.get('nome')
                    break
    
    return {
        "id": sen_id,
        "name": sen_data.get('full_name'),
        "gender": sen_data.get('gender'),
        "group": active_group
    }

def consolidate_atto(leg, atto_id):
    print(f"Consolidating data for Atto {atto_id}...")
    base_path = Path(f"data/Leg{leg}/{atto_id}")
    anagrafica_path = Path(f"data/Leg{leg}/Anagrafica/senatori_19.json")
    
    anagrafica = load_json(anagrafica_path)
    if not anagrafica:
        print("Error: Anagrafica not found. Run parser_anagrafica.py first.")
        return

    # 1. Load DDL Versions
    ddl_versions = {}
    for v in ["ddlpres", "ddlcomm", "ddlmess"]:
        v_dir = base_path / v
        if v_dir.exists():
            for f in v_dir.glob("*.json"):
                ddl_versions[v] = load_json(f)
                break # Take the first one

    # 2. Load and Enrich Amendments
    emend_dir = base_path / "emendc"
    enriched_amendments = []
    if emend_dir.exists():
        for f in emend_dir.glob("*.json"):
            amend = load_json(f)
            if not amend or "metadata" not in amend: continue
            
            amend_date = amend['metadata'].get('date')
            
            # Enrich proponents
            proponents = []
            for prop in amend['metadata'].get('proponents', []):
                p_href = prop.get('href', '')
                p_id = p_href.split('/')[-1] if p_href else prop.get('id')
                
                p_info = get_proponent_info(p_id, anagrafica, amend_date)
                # Fallback to name from XML if not found in anagrafica
                if "error" in p_info:
                    p_info["name"] = prop.get('name')
                    p_info["original_id"] = prop.get('id')
                
                proponents.append(p_info)
            
            amend['enriched_proponents'] = proponents
            enriched_amendments.append(amend)

    # 3. Extract DDL signatories from ddlpres
    firmatari_atto = []
    ddlpres = ddl_versions.get('ddlpres')
    if ddlpres:
        for prop in ddlpres.get('metadata', {}).get('proponents', []):
            firmatari_atto.append({
                "nome": prop.get('name'),
                "genere": prop.get('genere'),
                "primo_firmatario": prop.get('primo_firmatario', False)
            })

    # 4. Final Consolidation
    output = {
        "leg": leg,
        "atto_id": atto_id,
        "firmatari_atto": firmatari_atto,
        "ddl_versions": ddl_versions,
        "amendments": enriched_amendments
    }
    
    output_path = base_path / f"{atto_id}_consolidated.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Consolidated dataset saved to {output_path}")
    print(f"Total amendments enriched: {len(enriched_amendments)}")

def main():
    parser = argparse.ArgumentParser(description="Consolidate and enrich Atto data")
    parser.add_argument("--leg", default="19", help="Legislatura number")
    parser.add_argument("atto", help="Atto ID (e.g., Atto00055193)")
    args = parser.parse_args()

    consolidate_atto(args.leg, args.atto)

if __name__ == "__main__":
    main()
