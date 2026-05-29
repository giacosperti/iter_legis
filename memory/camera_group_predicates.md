---
name: camera-group-predicates
description: Camera triplestore uses ocd: predicates for group membership, NOT osr: as in Senato — confirmed empirically 2026-05-29
metadata:
  type: project
---

The Camera SPARQL endpoint uses completely different predicates for parliamentary group membership than the Senato endpoint. The `claudesss/claude_T_camera_v2.md` prompt (Query F) was wrong — it used `osr:` predicates that return 0 results.

**Correct Camera group chain (confirmed 2026-05-29):**

```sparql
?dep ocd:aderisce ?adG .                         # blank node
?adG ocd:rif_gruppoParlamentare ?gruppoURI ;
     ocd:startDate ?adG_start ;                  # YYYYMMDD
     ocd:endDate   ?adG_end .                    # YYYYMMDD (optional)
?adG rdfs:label ?gruppo_nome .                   # "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)"
?gruppoURI ocd:rif_leg <...legislatura...> .     # legislature filter
?gruppoURI dcterms:alternative ?gruppo_sigla .   # "PD"
```

**What does NOT work (returns 0 results):**
- `osr:legislatura`, `osr:gruppo`, `osr:inizio`, `osr:fine`, `osr:denominazione`
- These are Senato-only predicates. Camera's adesioneGruppo blank node ignores them.

**Note on group names:** `rdfs:label` on the adesioneGruppo blank node includes the date range, e.g. "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)". `dc:title` on the gruppoParlamentare URI appears truncated. Use the adG label for human-readable names.

**Note on deputies who changed groups:** sort by `adG_start DESC`, deduplicate on `uri_deputato` → keeps most recent group.

**Why:** Confirmed by inspecting properties of a known Leg17 deputy URI and its adesioneGruppo blank node. Applied fix in `fetch_metadati_camera_v2.py` QUERY_F (2026-05-29).

**How to apply:** Any future query for Camera parliamentary groups must use `ocd:rif_gruppoParlamentare`, `ocd:startDate`, and `dcterms:alternative`. Never use `osr:` predicates on the Camera endpoint for group data.
