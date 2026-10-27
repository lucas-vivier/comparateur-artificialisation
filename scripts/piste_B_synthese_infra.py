"""Piste B.3 — Part des flux OCS GE (devenu artificialisé, règle de référence) attribuable aux infrastructures (US4.1.x),
comparée aux destinations « routes » et « ferré » des Fichiers fonciers et à l'écart OCS GE − FF.
Entrées : outputs/tables/piste_B_usages_flux_<dep>.csv (piste_B_carroyage.py), piste_B_destinations_departements.csv.
Sortie : outputs/tables/piste_B_infrastructures_ecart.csv
"""
import pandas as pd
from occsol.paths import ROOT

T = ROOT / "outputs" / "tables"
DEPS = "75 77 78 91 92 93 94 95 02 59 60 62 80".split()
ff = pd.read_csv(T / "piste_B_destinations_departements.csv", dtype={"dep": str})
rows = []
for dep in DEPS:
    f = T / f"piste_B_usages_flux_{dep}.csv"
    if not f.exists():
        continue
    u = pd.read_csv(f, dtype={"dep": str}).set_index("code_us")
    ny = 4 if dep == "59" else 3
    per = "2021-2025" if dep == "59" else "2021-2024"
    tot = u.loc["TOTAL", "devenu_artif_ha_usage_fin"]
    g = lambda cs: float(u.loc[[c for c in cs if c in u.index], "devenu_artif_ha_usage_fin"].sum())  # noqa: E731
    rou, fer, autres = g(["US4.1.1"]), g(["US4.1.2"]), g(["US4.1.3", "US4.1.4", "US4.1.5"])
    trans, agri = g(["US6.1"]), g(["US1.1"])
    fr = ff[(ff.dep == dep) & (ff.periode == per)].iloc[0]
    ecart = tot - fr.total_ha
    infra = rou + fer + autres
    rows.append({"dep": dep, "periode": per, "ocs_devenu_artif_ha_an": round(tot / ny, 2),
                 "ocs_routes_US411_ha_an": round(rou / ny, 2), "ocs_fer_US412_ha_an": round(fer / ny, 2),
                 "ocs_autres_transports_US413_415_ha_an": round(autres / ny, 2),
                 "part_infra_dans_ocs": round(infra / tot, 4) if tot else None,
                 "ocs_zones_transition_US61_ha_an": round(trans / ny, 2), "ocs_agriculture_US11_ha_an": round(agri / ny, 2),
                 "ff_total_ha_an": round(fr.total_ha / ny, 2), "ff_routes_ferre_ha_an": round((fr.routes_ha + fr.ferre_ha) / ny, 2),
                 "ecart_ocs_moins_ff_ha_an": round(ecart / ny, 2),
                 "infra_ocs_moins_infra_ff_ha_an": round((infra - fr.routes_ha - fr.ferre_ha) / ny, 2),
                 "part_ecart_attribuable_infra": round((infra - fr.routes_ha - fr.ferre_ha) / ecart, 3) if ecart > 0 else None})
d = pd.DataFrame(rows)
tot = d.drop(columns=["dep", "periode"]).sum(numeric_only=True)
d.to_csv(T / "piste_B_infrastructures_ecart.csv", index=False)
print(d.to_string())
s = d.sum(numeric_only=True)
print("ensemble : infra OCS", round((s.ocs_routes_US411_ha_an + s.ocs_fer_US412_ha_an + s.ocs_autres_transports_US413_415_ha_an), 1),
      "ha/an sur", round(s.ocs_devenu_artif_ha_an, 1), "; écart", round(s.ecart_ocs_moins_ff_ha_an, 1), "; infra nette", round(s.infra_ocs_moins_infra_ff_ha_an, 1),
      "; US6.1", round(s.ocs_zones_transition_US61_ha_an, 1), "; US1.1", round(s.ocs_agriculture_US11_ha_an, 1))
