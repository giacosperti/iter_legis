import xml.etree.ElementTree as ET
import json
import os
import argparse

def parse_anagrafica(rdf_path):
    # Namespaces
    ns = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'osr': 'http://dati.senato.it/osr/',
        'foaf': 'http://xmlns.com/foaf/0.1/',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'ocd': 'http://dati.camera.it/ocd/'
    }
    
    print(f"Parsing {rdf_path}...")
    try:
        tree = ET.parse(rdf_path)
        root = tree.getroot()
    except Exception as e:
        return {"error": str(e)}

    senatori = {}
    gruppi = {}
    
    # 1. First pass: Identify nodeID mappings and Group names
    node_map = {}
    for desc in root.findall('rdf:Description', ns):
        node_id = desc.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}nodeID')
        if node_id:
            node_map[node_id] = desc

    # Resolve group names
    for desc in root.findall('rdf:Description', ns):
        about = desc.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')
        types = desc.findall('rdf:type', ns)
        is_gruppo = any(t.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource') in 
                        ['http://dati.camera.it/ocd/gruppoParlamentare', 'http://dati.senato.it/osr/Gruppo'] 
                        for t in types)
        
        if is_gruppo and "/gruppo/" in about:
            # Groups can have multiple denominations over time, we take the most recent one (without fine date) or the longest label
            denoms = []
            # Find all denominations for this group
            for d in root.findall('rdf:Description', ns):
                if d.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about') == about:
                    denom_link = d.find('osr:denominazione', ns)
                    if denom_link is not None:
                        node_id = denom_link.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}nodeID')
                        if node_id in node_map:
                            denom_node = node_map[node_id]
                            titolo = denom_node.find('osr:titolo', ns)
                            titolo_breve = denom_node.find('osr:titoloBreve', ns)
                            fine = denom_node.find('osr:fine', ns)
                            
                            name = titolo.text if titolo is not None else (titolo_breve.text if titolo_breve is not None else None)
                            if name:
                                denoms.append({"name": name, "fine": fine.text if fine is not None else None})
            
            if denoms:
                # Prefer one without a fine date
                current = [d for d in denoms if d['fine'] is None]
                if current:
                    gruppi[about] = current[0]['name']
                else:
                    gruppi[about] = denoms[-1]['name']

    # 2. Identify Senators
    for desc in root.findall('rdf:Description', ns):
        about = desc.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')
        types = desc.findall('rdf:type', ns)
        is_senatore = any(t.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource') == 'http://dati.senato.it/osr/Senatore' for t in types)
        
        if is_senatore and "/senatore/" in about:
            sen_id = about.split('/')[-1]
            if sen_id not in senatori:
                senatori[sen_id] = {"id": sen_id, "uri": about, "gruppi": []}

    # 3. Second pass: Extract details and memberships
    for desc in root.findall('rdf:Description', ns):
        about = desc.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')
        if "/senatore/" in about:
            sen_id = about.split('/')[-1]
            if sen_id in senatori:
                sen = senatori[sen_id]
                
                # Basic info
                label = desc.find('rdfs:label', ns)
                if label is not None: sen['full_name'] = label.text
                
                fname = desc.find('foaf:firstName', ns)
                if fname is not None: sen['first_name'] = fname.text
                
                lname = desc.find('foaf:lastName', ns)
                if lname is not None: sen['last_name'] = lname.text
                
                gender = desc.find('foaf:gender', ns)
                if gender is not None: sen['gender'] = gender.text
                
                birth = desc.find('osr:dataNascita', ns)
                if birth is not None: sen['birth_date'] = birth.text

                # Memberships (adesioni)
                for aderisce in desc.findall('{http://dati.camera.it/ocd/}aderisce', ns):
                    node_id = aderisce.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}nodeID')
                    if node_id in node_map:
                        node = node_map[node_id]
                        # Check if it's a group membership for Leg 19
                        leg = node.find('osr:legislatura', ns)
                        if leg is not None and leg.text == '19':
                            grp_uri_el = node.find('osr:gruppo', ns)
                            if grp_uri_el is not None:
                                grp_uri = grp_uri_el.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                                start_date = node.find('osr:inizio', ns)
                                end_date = node.find('osr:fine', ns)
                                sen['gruppi'].append({
                                    "uri": grp_uri,
                                    "nome": gruppi.get(grp_uri, "Unknown"),
                                    "inizio": start_date.text if start_date is not None else None,
                                    "fine": end_date.text if end_date is not None else None
                                })

    return {
        "senatori": list(senatori.values()),
        "gruppi": gruppi
    }

def main():
    parser = argparse.ArgumentParser(description="Parse Senato Anagrafica RDF")
    parser.add_argument("file", help="Path to the RDF file")
    parser.add_argument("--output", help="Path to save JSON output")
    args = parser.parse_args()

    result = parse_anagrafica(args.file)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Processed {len(result['senatori'])} senators. Saved to {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
