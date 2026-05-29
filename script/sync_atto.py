import subprocess
import json
import os
import argparse
import urllib.request
from pathlib import Path

def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        print(f"Error executing: {' '.join(cmd)}")
        print(result.stderr)
        return None
    return result.stdout

def download_file(url, local_path):
    try:
        urllib.request.urlretrieve(url, local_path)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def sync_atto(leg, atto):
    print(f"--- Syncing Atto {atto} (Leg{leg}) ---")
    base_dir = Path(f"data/Leg{leg}/{atto}")
    base_dir.mkdir(parents=True, exist_ok=True)

    # Sections to process with parser_ddl
    text_sections = ["ddlpres", "ddlcomm", "ddlmess"]
    
    for section in text_sections:
        section_dir = base_dir / section
        section_dir.mkdir(exist_ok=True)
        
        print(f"Checking {section}...")
        files_json = run_command(["uv", "run", "script/senato_pilot.py", "list-dir", f"Leg{leg}/{atto}/{section}"])
        if files_json:
            files = json.loads(files_json)
            for f in files:
                if f['type'] == 'file' and f['name'].endswith('.akn.xml'):
                    local_xml = section_dir / f['name']
                    local_json = section_dir / f['name'].replace('.akn.xml', '.json')
                    
                    if not local_xml.exists():
                        print(f"Downloading {f['name']}...")
                        download_file(f['download_url'], local_xml)
                    
                    if not local_json.exists():
                        print(f"Parsing {f['name']}...")
                        run_command(["uv", "run", "script/parser_ddl.py", local_xml.as_posix(), "--output", local_json.as_posix()])

    # 2. Process Committee Amendments (emendc)
    emendc_dir = base_dir / "emendc"
    emendc_dir.mkdir(exist_ok=True)
    
    print("Checking Committee Amendments...")
    files_json = run_command(["uv", "run", "script/senato_pilot.py", "list-dir", f"Leg{leg}/{atto}/emendc"])
    if files_json:
        files = json.loads(files_json)
        count = 0
        for f in files:
            if f['type'] == 'file' and f['name'].endswith('.akn.xml'):
                local_xml = emendc_dir / f['name']
                local_json = emendc_dir / f['name'].replace('.akn.xml', '.json')
                
                if not local_xml.exists():
                    download_file(f['download_url'], local_xml)
                
                if not local_json.exists() or local_json.stat().st_size < 200:
                    print(f"Parsing {f['name']}...")
                    run_command(["uv", "run", "script/parser_emendamenti.py", local_xml.as_posix(), "--output", local_json.as_posix()])
                
                count += 1
                if count % 20 == 0:
                    print(f"Processed {count} amendments...")
        print(f"Total amendments processed: {count}")

def main():
    parser = argparse.ArgumentParser(description="Sync and parse all data for a specific Atto")
    parser.add_argument("--leg", default="19", help="Legislatura number")
    parser.add_argument("atto", help="Atto ID (e.g., Atto00055193)")
    args = parser.parse_args()

    sync_atto(args.leg, args.atto)

if __name__ == "__main__":
    main()
