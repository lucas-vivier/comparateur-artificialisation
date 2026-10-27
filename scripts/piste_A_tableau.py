"""Piste A — agrège outputs/tables/piste_A/<dep>_dep.json et _communes.csv
-> outputs/tables/piste_A_validation_ign.csv (une ligne par département + total IDF / HdF / ensemble)
-> outputs/tables/piste_A_validation_ign_communes.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "tables" / "piste_A"
DEPS = ["75", "77", "78", "91", "92", "93", "94", "95", "02", "59", "60", "62", "80"]
REG = {d: ("IDF" if d[0] in "79" else "HdF") for d in DEPS}

rows = []
for d in DEPS:
    f = SRC / f"{d}_dep.json"
    if not f.exists():
        print("manquant", d)
        continue
    j = json.load(open(f))
    j.pop("datajson_dep", None)
    j["region"] = REG[d]
    j["nb_annees"] = int(j["periode"][-4:]) - 2021
    rows.append(j)
df = pd.DataFrame(rows)

# totaux régionaux (flux en ha/an additifs ; stocks additifs)
num = [c for c in df.columns if df[c].dtype.kind in "if" and c not in ("pas_grille_m", "nb_annees")]
tot = []
for lab, sub in (("IDF", df[df.region == "IDF"]), ("HdF", df[df.region == "HdF"]), ("ensemble", df)):
    t = sub[num].sum()
    t["dep"], t["region"], t["periode"] = lab, lab, "mixte (59 : 2021-2025)" if "59" in set(sub.dep) else "2021-2024"
    tot.append(t)
df = pd.concat([df, pd.DataFrame(tot)], ignore_index=True)


def pct(a, b):
    return np.where(df[b] != 0, 100 * (df[a] - df[b]) / df[b], np.nan)


out = pd.DataFrame({
    "dep": df.dep, "region": df.region, "periode": df.periode,
    # stocks (raster, même grille que data.json)
    "stock_2021_recalc_ha": df.recalc_stock_2021, "stock_2021_ign_ha": df.ign_stock_2021,
    "ecart_stock_2021_ha": df.recalc_stock_2021 - df.ign_stock_2021, "ecart_stock_2021_pct": pct("recalc_stock_2021", "ign_stock_2021"),
    "stock_y2_recalc_ha": df.recalc_stock_2024, "stock_y2_ign_ha": df.ign_stock_2024,
    "ecart_stock_y2_ha": df.recalc_stock_2024 - df.ign_stock_2024, "ecart_stock_y2_pct": pct("recalc_stock_2024", "ign_stock_2024"),
    # stocks vectoriels exacts (jointure par identifiant)
    "vec_stock_2021_recalc_ha": df.vec_2021_recalc_ha, "vec_stock_2021_ign_ha": df.vec_2021_ign_ha,
    "vec_2021_ign_seul_ha": df.vec_2021_ign_seul_ha, "vec_2021_recalc_seul_ha": df.vec_2021_recalc_seul_ha,
    "vec_2021_desaccord_crit_seuil_ha": df.vec_2021_desaccord_crit_seuil_ha,
    "vec_stock_y2_recalc_ha": df.vec_2024_recalc_ha, "vec_stock_y2_ign_ha": df.vec_2024_ign_ha,
    # flux bruts (ha/an)
    "artif_recalc_ha_an": df.recalc_artif_ha_an, "artif_ign_diff_ha_an": df.ign_diff_artif_ha_an,
    "ecart_artif_ha_an": df.recalc_artif_ha_an - df.ign_diff_artif_ha_an, "ecart_artif_pct": pct("recalc_artif_ha_an", "ign_diff_artif_ha_an"),
    "desartif_recalc_ha_an": df.recalc_desartif_ha_an, "desartif_ign_diff_ha_an": df.ign_diff_desartif_ha_an,
    "ecart_desartif_ha_an": df.recalc_desartif_ha_an - df.ign_diff_desartif_ha_an, "ecart_desartif_pct": pct("recalc_desartif_ha_an", "ign_diff_desartif_ha_an"),
    "net_recalc_ha_an": df.recalc_artif_ha_an - df.recalc_desartif_ha_an,
    "net_ign_diff_ha_an": df.ign_diff_artif_ha_an - df.ign_diff_desartif_ha_an,
    "diff_ign_vec_artif_ha_an": df.vec_diff_artif_ha / df.nb_annees.where(df.nb_annees > 0, np.nan),
    "diff_ign_vec_desartif_ha_an": df.vec_diff_desartif_ha / df.nb_annees.where(df.nb_annees > 0, np.nan),
    # part des flux expliqués par le patch correctif 2021
    "desartif_recalc_patch_ha_an": df.recalc_desartif_patch_ha_an,
    "part_desartif_recalc_patch_pct": 100 * df.recalc_desartif_patch_ha_an / df.recalc_desartif_ha_an,
    "artif_recalc_patch_ha_an": df.recalc_artif_patch_ha_an,
    "part_artif_recalc_patch_pct": 100 * df.recalc_artif_patch_ha_an / df.recalc_artif_ha_an,
    "net_recalc_hors_patch_ha_an": (df.recalc_artif_ha_an - df.recalc_artif_patch_ha_an) - (df.recalc_desartif_ha_an - df.recalc_desartif_patch_ha_an),
    "part_desartif_ign_patch_pct": 100 * df.ign_diff_desartif_patch_ha_an / df.ign_diff_desartif_ha_an,
    "part_artif_ign_patch_pct": 100 * df.ign_diff_artif_patch_ha_an / df.ign_diff_artif_ha_an,
    # typologie vectorielle des désartificialisations IGN (ha sur la période)
    "diff_desartif_patch_ha": df.diff_desartif_patch_ha,
    "diff_desartif_cs_change_us_identique_ha": df.diff_desartif_cs_change_us_identique_ha,
    "diff_desartif_us_change_ha": df.diff_desartif_us_change_ha,
    "diff_desartif_codes_identiques_ha": df.diff_desartif_codes_identiques_ha,
    "patch_ha": df.patch_ha, "patch_vers_artif_ha": df.patch_vers_artif_ha, "patch_vers_non_artif_ha": df.patch_vers_non_artif_ha,
    "pas_grille_m": df.pas_grille_m,
})
out.round(3).to_csv(ROOT / "outputs" / "tables" / "piste_A_validation_ign.csv", index=False)
coms = [pd.read_csv(f, dtype={"insee": str, "dep": str}) for f in sorted(SRC.glob("*_communes.csv"))]
if coms:
    pd.concat(coms).to_csv(ROOT / "outputs" / "tables" / "piste_A_validation_ign_communes.csv", index=False)
pd.set_option("display.width", 250)
print(out[["dep", "ecart_stock_2021_ha", "ecart_stock_2021_pct", "ecart_stock_y2_pct", "artif_recalc_ha_an", "artif_ign_diff_ha_an",
           "ecart_artif_pct", "desartif_recalc_ha_an", "desartif_ign_diff_ha_an", "ecart_desartif_pct",
           "part_desartif_recalc_patch_pct", "part_artif_recalc_patch_pct", "net_recalc_ha_an", "net_recalc_hors_patch_ha_an"]].round(2).to_string())
