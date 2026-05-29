# claude_T5.md — fetch_emendamenti_senato.py

## Obiettivo

Scaricare i file AKN degli emendamenti Senato per tutti i DDL con `has_emendamenti_akn = True`.

## Input

`data/meta/atti_senato.parquet` — filtrare `has_emendamenti_akn == True`

## Output

- `data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml`
- `data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml.meta.json`
- `data/meta/fetch_log_emendamenti_senato.json`

## Query SPARQL per lista emendamenti

```sparql
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?emend ?url_xml ?url_testo ?tipo ?numero ?flag_comm WHERE {
  ?emend a osr:Emendamento ;
         osr:oggetto ?ogg ;
         osr:URLTestoXml ?url_xml .
  ?ogg osr:relativoA <{ddl_uri}> .
  OPTIONAL { ?emend osr:URLTesto     ?url_testo  }
  OPTIONAL { ?emend osr:tipo         ?tipo       }
  OPTIONAL { ?emend osr:numero       ?numero     }
  OPTIONAL { ?emend osr:flagCommissione ?flag_comm }
}
```

Nota: `osr:URLTesto` è un redirect `.asp` che punta allo stesso file AKN di `osr:URLTestoXml`. Non è un formato alternativo.

## Encoding — CRITICO

I file AKN Senato NON hanno encoding uniforme:

| Legislatura | Encoding |
|---|---|
| Leg14 | UTF-8 con BOM |
| Leg18 | UTF-16 LE |
| Leg19 | ISO-8859-1 |

Usare `chardet` per rilevamento automatico:
```python
import chardet

def detect_and_decode(raw_bytes: bytes) -> str:
    # Check BOM first, then chardet
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        return raw_bytes[3:].decode('utf-8')
    if raw_bytes.startswith(b'\xff\xfe'):
        return raw_bytes.decode('utf-16-le')
    detected = chardet.detect(raw_bytes)
    return raw_bytes.decode(detected['encoding'] or 'utf-8', errors='replace')
```

## Copertura e qualità dei dati

| Leg | Emend. triplestore | Copertura attesa |
|---|---|---|
| 13 | 709 | ~20% (catena spezzata) |
| 14 | 86.147 | ~90% |
| 15 | 33.652 | ~97% |
| 16 | 116.909 | ~138% (doppio conteggio testi unificati) |
| 17 | 253.387 | ~100% |
| 18 | 151.262 | ~98% |
| 19 | 53.337 | ~100% (parziale) |

Emendamenti orfani (~6–9%) non recuperabili — catena `osr:oggetto → osr:relativoA` spezzata. Non trattarli come errori.
`tipodoc=emend` = aula, `tipodoc=emendc` = commissione (NON "Camera").

## Convenzioni

- Script in `script_prova/fetch_emendamenti_senato.py`
- CLI: `--legs`, `--force`, `--dry-run`, `--limit-ddl`
- Sleep 0.5s tra download, retry 3×, idempotenza
- Dipendenza aggiuntiva: `chardet`
