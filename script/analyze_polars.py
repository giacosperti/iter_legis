import duckdb
import polars as pl
from pathlib import Path

def analyze_complexity(db_path):
    print(f"Connecting to DuckDB at {db_path}...")
    con = duckdb.connect(str(db_path))

    # 1. Query metrics from DuckDB into Polars
    # We calculate word count directly in SQL for efficiency, then move to Polars
    query = """
    SELECT 
        atto_id, 
        numero_articolo, 
        versione,
        LENGTH(testo_integrale) as char_count,
        ARRAY_LENGTH(STR_SPLIT_REGEX(testo_integrale, '\\s+')) as word_count
    FROM t_articoli
    """
    
    # DuckDB arrow() export is very fast for Polars
    # Normalize numero_articolo: remove "Art.", spaces and final dots
    df_articoli = (
        con.execute(query).pl()
        .with_columns(
            pl.col("numero_articolo")
            .str.replace("Art.", "")
            .str.replace_all(r"\s+", "")
            .str.replace(r"\.$", "")
            .alias("num_clean")
        )
    )
    
    print("\n--- Articoli Metrics (Polars) ---")
    print(df_articoli.select(["num_clean", "versione", "word_count"]).head())

    # 2. Pivot to compare ddlpres (Start) vs ddlmess (End)
    df_comparison = (
        df_articoli
        .filter(pl.col("versione").is_in(["ddlpres", "ddlmess"]))
        .pivot(
            on="versione",
            index=["atto_id", "num_clean"],
            values="word_count"
        )
        .with_columns([
            (pl.col("ddlmess").fill_null(0) - pl.col("ddlpres").fill_null(0)).alias("delta_words")
        ])
    )

    print("\n--- Growth Analysis (Inizio vs Fine) ---")
    print(df_comparison.sort(pl.col("num_clean").cast(pl.Int64, strict=False)))

    # 3. Join with Amendments fragmentation
    query_emend = """
    SELECT
        e.articolo_target as num_clean,
        COUNT(DISTINCT e.emendamento_id) as num_emendamenti,
        COUNT(DISTINCT p.proponente_gruppo) as num_gruppi_coinvolti
    FROM t_emendamenti e
    LEFT JOIN t_proponenti p ON e.emendamento_id = p.emendamento_id
    GROUP BY e.articolo_target
    """
    df_emend = con.execute(query_emend).pl()

    df_final = df_comparison.join(df_emend, on="num_clean", how="left")
    
    print("\n--- Final Correlation: Fragmentation vs Complexity ---")
    print(df_final.sort("delta_words", descending=True))

    con.close()

if __name__ == "__main__":
    db_file = Path("data/iter_legis.duckdb")
    if db_file.exists():
        analyze_complexity(db_file)
    else:
        print("Error: Database not found. Run init_duckdb.py first.")
