"""Piste B.1 — Fichiers fonciers (Cerema CONSOENAF) : alignement des périodes et décomposition par destination.

Source : data/raw/cerema/conso_com_2011_2025.csv (m², flux annuel entre deux 1er janvier : naf21art22 = 2021->2022).
Périodes : 2021-2024 (3 ans, comparée à OCS GE 2021->2024) ; 2021-2025 (4 ans, comparée au MOS 2021->2025 et à OCS GE Nord 2021->2025).
Sorties : outputs/tables/piste_B_destinations_departements.csv, piste_B_comparaison_periodes.csv
"""
import json
import pandas as pd
from occsol.paths import RAW, ROOT

DEPS = "75 77 78 91 92 93 94 95 02 59 60 62 80".split()
DEST = {"hab": "habitat", "act": "activite", "mix": "mixte", "rou": "routes", "fer": "ferre", "inc": "inconnu"}
ANS = ["21", "22", "23", "24"]
cols = ["idcom", "iddep"] + [f"naf{a}art{int(a)+1}" for a in ANS] + [f"art{a}{d}{int(a)+1}" for a in ANS for d in DEST]
c = pd.read_csv(RAW / "cerema" / "conso_com_2011_2025.csv", dtype={"idcom": str, "iddep": str}, usecols=cols, low_memory=False)
c = c[c.iddep.isin(DEPS)]
rows = []
for dep, g in c.groupby("iddep"):
    for per, ans in [("2021-2024", ANS[:3]), ("2021-2025", ANS)]:
        tot = sum(g[f"naf{a}art{int(a)+1}"].sum() for a in ans) / 1e4
        r = {"dep": dep, "periode": per, "nb_annees": len(ans), "total_ha": round(tot, 2), "total_ha_an": round(tot / len(ans), 2)}
        s = 0
        for k, lab in DEST.items():
            v = sum(g[f"art{a}{k}{int(a)+1}"].sum() for a in ans) / 1e4
            s += v
            r[f"{lab}_ha"] = round(v, 2)
            r[f"part_{lab}"] = round(v / tot, 4) if tot else None
        r["ecart_somme_destinations_ha"] = round(tot - s, 3)
        rows.append(r)
d = pd.DataFrame(rows)
d["dep"] = pd.Categorical(d.dep, DEPS, ordered=True)
d = d.sort_values(["periode", "dep"])
out = ROOT / "outputs" / "tables"
d.to_csv(out / "piste_B_destinations_departements.csv", index=False)

# comparaison avec les flux bruts déjà calculés (web/<dep>/data.json)
cmp = []
for dep in DEPS:
    j = json.loads((ROOT / "web" / dep / "data.json").read_text())["departement"]
    ocs_per = "2021-2025" if dep == "59" else "2021-2024"
    ff_o = d[(d.dep == dep) & (d.periode == ocs_per)].iloc[0]
    mos_per = "2021-2024" if dep in {"02", "60", "62", "80"} else "2021-2025"  # OCS2D HdF : 2021->2024 sauf Nord
    ff_m = d[(d.dep == dep) & (d.periode == mos_per)].iloc[0]
    o = j["flux_brut"]["reference"]["artif"]
    m = j["mos"]["conso_brute_ha_an"]
    cmp.append({"dep": dep, "ocsge_periode": ocs_per, "ocsge_brut_ha_an": o, "ff_meme_periode_ha_an": ff_o.total_ha_an,
                "ratio_ff_sur_ocsge": round(ff_o.total_ha_an / o, 3) if o else None,
                "ff_hors_routes_fer_ha_an": round(ff_o.total_ha_an - (ff_o.routes_ha + ff_o.ferre_ha) / ff_o.nb_annees, 2),
                "mos_ocs2d_periode": mos_per,
                "mos_ocs2d_brut_ha_an": m, "ff_meme_periode_mos_ha_an": ff_m.total_ha_an,
                "ratio_ff_sur_mos": round(ff_m.total_ha_an / m, 3) if m else None})
pd.DataFrame(cmp).to_csv(out / "piste_B_comparaison_periodes.csv", index=False)
print(d.to_string())
print(pd.DataFrame(cmp).to_string())
