import xml.etree.ElementTree as ET
import json
import sys
import argparse
import os

def parse_amendment(xml_path):
    # Namespace dictionary
    ns = {'an': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03'}
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        return {"error": str(e)}

    # 1. Identification and Metadata
    metadata = {}
    work = root.find('.//an:FRBRWork', ns)
    if work is not None:
        metadata['id'] = work.find('an:FRBRthis', ns).attrib.get('value') if work.find('an:FRBRthis', ns) is not None else ""
        metadata['date'] = work.find('an:FRBRdate', ns).attrib.get('date') if work.find('an:FRBRdate', ns) is not None else ""
        metadata['number'] = work.find('an:FRBRnumber', ns).attrib.get('value') if work.find('an:FRBRnumber', ns) is not None else ""
        metadata['name'] = work.find('an:FRBRname', ns).attrib.get('value') if work.find('an:FRBRname', ns) is not None else ""

    # Active Reference (Target DDL)
    active_ref = root.find('.//an:references/an:activeRef', ns)
    if active_ref is not None:
        metadata['target_ddl'] = active_ref.attrib.get('href')
        metadata['target_ddl_showAs'] = active_ref.attrib.get('showAs')

    # 2. Proponents
    proponents = []
    # Map person IDs to names from references
    person_map = {}
    for person in root.findall('.//an:references/an:TLCPerson', ns):
        p_id = person.attrib.get('id')
        p_name = person.attrib.get('showAs')
        p_href = person.attrib.get('href')
        person_map[p_id] = {"name": p_name, "href": p_href}

    # Extract proponents from preface
    for prop in root.findall('.//an:preface//an:docProponent', ns):
        ref_id = prop.attrib.get('refersTo', '').lstrip('#')
        p_info = person_map.get(ref_id, {"name": prop.text.strip() if prop.text else ""})
        proponents.append({
            "id": ref_id,
            "name": p_info.get("name"),
            "href": p_info.get("href")
        })
    metadata['proponents'] = proponents

    # 3. Amendment Content (The actual changes)
    amendment_body = root.find('.//an:amendmentBody', ns)
    content = []
    if amendment_body is not None:
        for p in amendment_body.findall('.//an:p', ns):
            text = "".join(p.itertext()).strip()
            if text:
                content.append(text)

    # Attempt to extract target article/comma from docNumber or content
    # In AKN, docNumber usually contains "Emendamento n. 3.1" (Article 3, Amendment 1)
    doc_num_el = root.find('.//an:preface/an:p/an:docNumber', ns)
    target_info = ""
    if doc_num_el is not None:
        target_info = doc_num_el.text.strip()

    return {
        "metadata": metadata,
        "target_info": target_info,
        "content": content,
        "source": xml_path
    }

def main():
    parser = argparse.ArgumentParser(description="Parse Akoma Ntoso Amendment XML")
    parser.add_argument("file", help="Path to the XML file")
    parser.add_argument("--output", help="Path to save JSON output")
    args = parser.parse_args()

    result = parse_amendment(args.file)
    
    if args.output:
        # Idempotence: Ensure directory exists
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Result saved to {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
