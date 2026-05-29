import duckdb
import json
from pathlib import Path

def setup_database(db_path):
    print(f"Initializing DuckDB at {db_path}...")
    con = duckdb.connect(str(db_path))
    
    # Create tables based on our ER schema
    con.execute("""
        CREATE TABLE IF NOT EXISTS t_atti (
            atto_id VARCHAR PRIMARY KEY,
            legislatura VARCHAR
        );

        CREATE TABLE IF NOT EXISTS t_firmatari_atto (
            atto_id VARCHAR,
            nome VARCHAR,
            genere VARCHAR,
            primo_firmatario BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS t_articoli (
            atto_id VARCHAR,
            articolo_id VARCHAR,
            numero_articolo VARCHAR,
            titolo VARCHAR,
            versione VARCHAR,
            testo_integrale VARCHAR,
            PRIMARY KEY (atto_id, articolo_id, versione)
        );

        CREATE TABLE IF NOT EXISTS t_emendamenti (
            atto_id VARCHAR,
            emendamento_id VARCHAR,
            numero_emendamento VARCHAR,
            articolo_target VARCHAR,
            data DATE,
            target_info VARCHAR,
            testo_emendamento VARCHAR,
            PRIMARY KEY (emendamento_id)
        );

        CREATE TABLE IF NOT EXISTS t_proponenti (
            emendamento_id VARCHAR,
            proponente_id VARCHAR,
            proponente_nome VARCHAR,
            proponente_gruppo VARCHAR,
            proponente_genere VARCHAR
        );

        CREATE TABLE IF NOT EXISTS t_senatori (
            senatore_id VARCHAR,
            full_name VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            gender VARCHAR,
            birth_date DATE,
            gruppo_nome VARCHAR,
            gruppo_inizio DATE,
            gruppo_fine DATE,
            gruppo_uri VARCHAR
        );
    """)
    return con

def import_anagrafica(con, csv_path):
    print(f"Importing anagrafica from {csv_path}...")
    con.execute(f"INSERT INTO t_senatori SELECT * FROM read_csv_auto('{csv_path}')")
    count = con.execute("SELECT count(*) FROM t_senatori").fetchone()[0]
    print(f"Total rows in t_senatori: {count}")

def import_atto_csvs(con, flattened_dir):
    print(f"Importing Atto data from {flattened_dir}...")
    
    # Import Atti
    con.execute(f"INSERT OR IGNORE INTO t_atti SELECT * FROM read_csv_auto('{flattened_dir}/t_atti.csv')")
    
    # Import Firmatari Atto (idempotent via atto_id check)
    atto_id = con.execute(f"SELECT atto_id FROM read_csv_auto('{flattened_dir}/t_atti.csv') LIMIT 1").fetchone()[0]
    firmatari_exists = con.execute(f"SELECT count(*) FROM t_firmatari_atto WHERE atto_id = '{atto_id}'").fetchone()[0]
    if firmatari_exists == 0:
        con.execute(f"INSERT INTO t_firmatari_atto SELECT * FROM read_csv_auto('{flattened_dir}/t_firmatari_atto.csv')")

    # Import Articoli
    con.execute(f"INSERT OR IGNORE INTO t_articoli SELECT * FROM read_csv_auto('{flattened_dir}/t_articoli.csv')")
    
    # Import Emendamenti (idempotent via PRIMARY KEY)
    con.execute(f"INSERT OR IGNORE INTO t_emendamenti SELECT * FROM read_csv_auto('{flattened_dir}/t_emendamenti.csv')")

    # Import Proponenti (idempotent: skip if emendamento_id already present)
    em_ids = con.execute(f"SELECT DISTINCT emendamento_id FROM t_emendamenti WHERE atto_id = '{atto_id}'").fetchall()
    if em_ids:
        exists = con.execute(
            f"SELECT count(*) FROM t_proponenti WHERE emendamento_id = '{em_ids[0][0]}'"
        ).fetchone()[0]
        if exists == 0:
            con.execute(f"INSERT INTO t_proponenti SELECT * FROM read_csv_auto('{flattened_dir}/t_proponenti.csv')")
        else:
            print(f"Proponents for {atto_id} already in database. Skipping.")
    
    print(f"Import of {atto_id} complete.")

if __name__ == "__main__":
    db_file = Path("data/iter_legis.duckdb")
    anagrafica_csv = Path("data/Leg19/Anagrafica/senatori_19_flattened.csv")
    
    con = setup_database(db_file)
    
    # Import anagrafica (idempotent via manual check or temporary table)
    sen_exists = con.execute("SELECT count(*) FROM t_senatori").fetchone()[0]
    if sen_exists == 0 and anagrafica_csv.exists():
        import_anagrafica(con, anagrafica_csv)

    # Process all available Acts in data folder
    for leg_dir in Path("data").glob("Leg*"):
        for atto_dir in leg_dir.glob("Atto*"):
            flattened = atto_dir / "flattened_custom"
            if flattened.exists():
                import_atto_csvs(con, flattened)
    
    con.close()
