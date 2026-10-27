"""Piste C — synthèse : familles d'écarts par département / région, effet des variantes (pixel + data.json).

Usage : python scripts/piste_C_synthese.py   (léger : lit outputs/tables/piste_C/*.csv et web/<dep>/data.json)
"""
from __future__ import annotations

import json

import pandas as pd

from occsol.paths import ROOT

T = ROOT / "outputs" / "tables"
D = T / "piste_C"
DEPS = ["75", "77", "78", "91", "92", "93", "94", "95", "02", "59", "60", "62", "80"]
HDF = {"02", "59", "60", "62", "80"}
REG = lambda d: "HdF" if d in HDF else "IDF"  # noqa: E731
VARS = ["reference", "sans_herbace", "seuil_0", "seuil_1000", "seuil_5000"]


def familles():
    f = pd.concat([pd.read_csv(D / f"{d}_familles.csv", dtype={"dep": str}) for d in DEPS])
    f["region"] = f.dep.map(REG)
    rows = []
    for key, g in [*((d, f[f.dep == d]) for d in DEPS), ("IDF", f[f.region == "IDF"]), ("HdF", f[f.region == "HdF"]), ("Ensemble", f)]:
        t = g.groupby(["sens", "famille"]).ha.sum().reset_index()
        t["part"] = t.ha / t.groupby("sens").ha.transform("sum")
        t.insert(0, "territoire", key)
        rows.append(t)
    out = pd.concat(rows)
    out["ha"] = out.ha.round(1)
    out["part"] = out.part.round(4)
    out.to_csv(T / "piste_C_familles.csv", index=False)
    return out


def matrice():
    m = pd.concat([pd.read_csv(D / f"{d}_matrice.csv", dtype={"dep": str}, low_memory=False) for d in DEPS])
    m["region"] = m.dep.map(REG)
    # matrice régionale CS x US x classe régionale (poste MOS ou classe enaf OCS2D)
    g = (m.groupby(["region", "sens", "famille", "cs", "us", "r_classe"], dropna=False).ha.sum().round(1)
         .reset_index().sort_values(["region", "sens", "ha"], ascending=[True, True, False]))
    g = g[g.ha >= 1]
    g.to_csv(T / "piste_C_matrice_cs_us_regional.csv", index=False)
    # IDF au poste MOS (79 postes)
    i = m[m.region == "IDF"].groupby(["sens", "r_poste", "r_classe"]).ha.sum().round(1).reset_index()
    i["r_poste"] = i.r_poste.astype(int)
    i.sort_values(["sens", "ha"], ascending=[True, False]).to_csv(T / "piste_C_matrice_postes_mos_idf.csv", index=False)
    # par département : CS x US sur les désaccords (somme des 2 sens séparés)
    dcsus = m.groupby(["dep", "sens", "cs", "us"]).ha.sum().round(1).reset_index()
    dcsus[dcsus.ha >= 1].sort_values(["dep", "sens", "ha"], ascending=[True, True, False]).to_csv(
        T / "piste_C_matrice_cs_us_departements.csv", index=False)
    # détail famille b : bascule au seuillage vs contour
    b = m[m.famille == "b_seuil_generalisation"].groupby(["region", "sens", "detail_seuil"]).ha.sum().round(1).reset_index()
    b.to_csv(T / "piste_C_detail_seuil.csv", index=False)
    # résidu : principaux couples
    r = (m[m.famille == "e_residu"].groupby(["region", "sens", "cs", "us", "r_classe"], dropna=False).ha.sum().round(1)
         .reset_index().sort_values("ha", ascending=False).groupby(["region", "sens"]).head(10))
    r.to_csv(T / "piste_C_residu_top.csv", index=False)
    # famille a en D1 : part sur usages de transport / réseaux
    a = m[(m.famille == "a_herbace_espaces_verts") & (m.sens.str.startswith("D1"))].copy()
    a["us_groupe"] = a.us.astype(str).str.extract(r"^(US\d)")[0]
    a.groupby(["region", "us_groupe"]).ha.sum().round(1).reset_index().to_csv(T / "piste_C_herbace_par_usage.csv", index=False)
    return g, i, b, r


def variantes():
    v = pd.concat([pd.read_csv(D / f"{d}_variantes.csv", dtype={"dep": str}) for d in DEPS])
    rows = []
    for d in DEPS:
        j = json.loads((ROOT / "web" / d / "data.json").read_text())["departement"]
        mo = j["mos"]
        for var in VARS:
            rows.append({"dep": d, "variante": var, "stock_ocs_2021_ha": j["stock"][var]["2021"],
                         "urbain_reg_2021_ha": mo["urbain_2021"],
                         "flux_brut_ocs_ha_an": j["flux_brut"][var]["artif"], "flux_net_ocs_ha_an": j["flux"][var]["2021-2024"],
                         "conso_brute_reg_ha_an": mo["conso_brute_ha_an"], "conso_nette_reg_ha_an": mo["conso_nette_ha_an"],
                         "accord_2021_datajson_ref": mo["accord_2021"] if var == "reference" else None})
    j = pd.DataFrame(rows)
    out = v.merge(j, on=["dep", "variante"])
    out["region"] = out.dep.map(REG)
    agg = []
    for key, g in [("IDF", out[out.region == "IDF"]), ("HdF", out[out.region == "HdF"]), ("Ensemble", out)]:
        s = g.groupby("variante")[["ocs_seul_ha", "reg_seul_ha", "ocs_artif_ha", "reg_urbain_ha", "stock_ocs_2021_ha",
                                   "urbain_reg_2021_ha", "flux_brut_ocs_ha_an", "flux_net_ocs_ha_an",
                                   "conso_brute_reg_ha_an", "conso_nette_reg_ha_an"]].sum().reset_index()
        s["dep"] = key
        agg.append(s)
    a = pd.concat(agg)
    # surface commune = (désaccords) / (1 - accord) ; on la recalcule par département puis on somme
    out["surf_commune_ha"] = (out.ocs_seul_ha + out.reg_seul_ha) / (1 - out.accord_pixel)
    sc = {k: out[(out.variante == "reference") & ((out.region == k) | (k == "Ensemble"))].surf_commune_ha.sum()
          for k in ["IDF", "HdF", "Ensemble"]}
    a["accord_pixel"] = 1 - (a.ocs_seul_ha + a.reg_seul_ha) / a.dep.map(sc)
    res = pd.concat([out.drop(columns=["surf_commune_ha", "region"]), a], ignore_index=True)
    res["ecart_stock_ha"] = res.ocs_artif_ha - res.reg_urbain_ha
    res["ratio_flux_brut"] = res.flux_brut_ocs_ha_an / res.conso_brute_reg_ha_an
    res["ratio_flux_net"] = res.flux_net_ocs_ha_an / res.conso_nette_reg_ha_an
    for c in res.columns:
        if res[c].dtype.kind == "f":
            res[c] = res[c].round(4 if c.startswith(("accord", "ratio")) else 1)
    res.to_csv(T / "piste_C_variantes_accord.csv", index=False)
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    f = familles()
    print(f[f.territoire.isin(["IDF", "HdF", "Ensemble"])].to_string())
    g, i, b, r = matrice()
    print(b.to_string())
    print(r.to_string())
    print(i.groupby("sens").head(12).to_string())
    v = variantes()
    print(v[v.dep.isin(["IDF", "HdF", "Ensemble"])].to_string())
