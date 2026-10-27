"""Contrôles des extensions 1 (départements IDF) et 2 (échelle communale) à partir de web/<dep>/data.json.

Usage : python scripts/analyse_extensions.py  -> outputs/tables/extensions_idf.csv + résumé imprimé
"""
import json

import numpy as np
import pandas as pd

from occsol.paths import ROOT, TABLES

DEPS = ["75", "77", "78", "91", "92", "93", "94", "95", "02", "59", "60", "62", "80"]
REG = {d: ("HDF" if d in {"02", "59", "60", "62", "80"} else "IDF") for d in DEPS}
rows, com = [], []
for d in DEPS:
    f = ROOT / "web" / d / "data.json"
    if not f.exists():
        continue
    D = json.loads(f.read_text())
    dep = D["departement"]
    rows.append({"dep": d, "region": REG[d], "surface_ha": dep["surface_ha"],
                 "ocs_artif_2021": dep["stock"]["reference"]["2021"], "mos_urbain_2021": dep["mos"]["urbain_2021"],
                 "accord_2021": dep["mos"]["accord_2021"], "ocs_seul_ha": dep["mos"]["ocs_seul_ha"], "mos_seul_ha": dep["mos"]["mos_seul_ha"],
                 "ocs_brut": dep["flux_brut"]["reference"]["artif"], "ocs_desartif": dep["flux_brut"]["reference"]["desartif"],
                 "ocs_net": dep["flux"]["reference"]["2021-2024"], "mos_brut": dep["mos"]["conso_brute_ha_an"],
                 "mos_net": dep["mos"]["conso_nette_ha_an"], "ff_brut": dep["cerema"]["2021-2024"],
                 "res_carte_m": D["res_m"]})
    for c, v in D["indicateurs"].items():
        if "mos" not in v:
            continue
        com.append({"dep": d, "region": REG[d], "insee": c, "surface": v["surface_ha"], "ocs_brut": v["flux_brut"]["reference"]["artif"],
                    "ocs_net": v["flux"]["reference"]["2021-2024"], "mos_brut": v["mos"]["conso_brute_ha_an"],
                    "ff": (v.get("cerema") or {}).get("2021-2024"), "accord": v["mos"]["accord_2021"]})
t = pd.DataFrame(rows)
TABLES.mkdir(parents=True, exist_ok=True)
t.to_csv(TABLES / "extensions_idf_departements.csv", index=False)
c = pd.DataFrame(com)
c.to_csv(TABLES / "extensions_idf_communes.csv", index=False)
pd.set_option("display.width", 220)
print(t.round(2).to_string(index=False))
for reg, tt in t.groupby("region"):
    print(reg, tt[["surface_ha", "ocs_artif_2021", "mos_urbain_2021", "ocs_seul_ha", "mos_seul_ha", "ocs_brut", "ocs_desartif", "ocs_net", "mos_brut", "mos_net", "ff_brut"]].sum().round(1).to_dict())
tot = t[["surface_ha", "ocs_artif_2021", "mos_urbain_2021", "ocs_seul_ha", "mos_seul_ha", "ocs_brut", "ocs_desartif", "ocs_net", "mos_brut", "mos_net", "ff_brut"]].sum()
print("\nIDF :", tot.round(1).to_dict())
# Extension 2 : bruit communal. Une tache minimale OCS GE hors zone construite = 2 500 m² ; sur 3 ans -> 0,08 ha/an.
seuil = 0.25 / 3
for reg, cc in c.groupby("region"):
    print(reg, "communes", len(cc), "; part < 0,08 ha/an : OCS GE", round(100*(cc.ocs_brut < 0.25/3).mean()), "% ; base régionale", round(100*(cc.mos_brut < 0.25/3).mean()), "% ; FF", round(100*(cc.ff.dropna() < 0.25/3).mean()), "%")
print(f"\nCommunes : {len(c)}")
for col in ["ocs_brut", "mos_brut", "ff"]:
    x = c[col].dropna()
    print(f"  {col}: médiane {x.median():.2f} ha/an ; part < {seuil:.2f} ha/an (une tache de 2 500 m² en 3 ans) : {100*(x < seuil).mean():.0f} %")
for a, b in [("ocs_brut", "ff"), ("mos_brut", "ff"), ("ocs_brut", "mos_brut")]:
    x = c[[a, b]].dropna()
    print(f"  corrélation de rang {a} / {b} : {x[a].rank().corr(x[b].rank()):.2f} (n={len(x)})")
print("  accord communal : médiane", round(c.accord.median(), 3), "; 10e centile", round(c.accord.quantile(.1), 3))
