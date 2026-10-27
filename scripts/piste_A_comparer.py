"""Piste A — validation du recalcul OCS GE (variante reference) contre les couches officielles IGN.

Usage (un département à la fois, sous verrou) :
    flock /home/claude/occsol/.heavy.lock python scripts/piste_A_comparer.py 94

Entrées :
  data/processed/<dep>/ocsge_<a>.parquet + artif_<a>.parquet (recalcul, même ordre que OCCUPATION_SOL.gpkg brut)
  data/processed/<dep>/x_<a>/**/OCCUPATION_SOL.gpkg (identifiants des polygones)
  data/raw/ign_artif/artif/*.7z        couche OCSGE-ARTIFICIALISATION (millésimes)
  data/raw/ign_artif/artif_diff/*.7z   OCSGE-ARTIFICIALISATION DIFF (zan_evol : +1 artif / -1 désartif)
  data/raw/ign_artif/patch/*.7z        OCSGE PATCHCORRECTIF 2021
Sorties : outputs/tables/piste_A/<dep>_communes.csv, <dep>_dep.json

Méthode :
  * même grille que pipeline_dep.py (emprise des communes, pas 5/10/15 m, index communal) ;
    les stocks et flux « recalculés » sont donc ceux de web/<dep>/data.json (contrôle d'égalité) ;
  * couche IGN rastérisée sur la même grille -> écarts dus à la seule classification ;
  * en complément, comparaison vectorielle exacte polygone par polygone (jointure sur l'identifiant
    OCS GE, surface = champ « aire » de la couche IGN) ;
  * patch correctif : statut « brut » (avant seuillage) recalculé avec les codes d'origine et les
    codes corrigés ; un patch « explique » un retour si la correction fait passer le polygone 2021
    d'artificialisé à non artificialisé (type 3), une artificialisation si l'inverse (type 2).
"""
from __future__ import annotations

import gc
import glob
import json
import math
import shutil
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import py7zr
import pyarrow.parquet as pq
import pyogrio
import rasterio.features
from rasterio.transform import from_origin

from occsol.nomenclature import Regle, classer_brut
from occsol.paths import PROCESSED, RAW, ROOT

IGN = RAW / "ign_artif"
OUT = ROOT / "outputs" / "tables" / "piste_A"
TMP = Path("/tmp/claude-0/-home-claude/b24a0306-eeda-5a86-8be1-519ef7c38189/scratchpad/piste_A")
Y2 = {"59": "2025"}
B = 50_000


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def extraire(pattern: str, dest: Path) -> Path:
    arch = sorted(glob.glob(str(pattern)))
    assert len(arch) == 1, (pattern, arch)
    dest.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(arch[0]) as z:
        names = [n for n in z.getnames() if n.endswith(".gpkg")]
        z.extract(dest, targets=names)
    g = sorted(dest.rglob("*.gpkg"))
    assert len(g) == 1, g
    return g[0]


def main(dep: str):
    z3 = f"D{dep.zfill(3)}"
    y2 = Y2.get(dep, "2024")
    NY = int(y2) - 2021
    out = PROCESSED / dep
    tmp = TMP / dep
    shutil.rmtree(tmp, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    R = Regle.reference()

    # ---------------- grille identique à pipeline_dep.web_stats
    com = gpd.read_file(RAW / "communes" / f"communes_{dep}.geojson").to_crs(2154).rename(columns={"code": "insee"})
    com = com[["insee", "nom", "geometry"]].reset_index(drop=True)
    x0, y0, x1, y1 = com.total_bounds
    rs = 5.0 if (x1 - x0) * (y1 - y0) / 25 < 1.5e8 else (10.0 if (x1 - x0) * (y1 - y0) / 100 < 6e7 else 15.0)
    W5, H5 = int(math.ceil((x1 - x0) / rs)), int(math.ceil((y1 - y0) / rs))
    tr5 = from_origin(x0, y1, rs, rs)
    shape = (H5, W5)

    def burn(geo, vals, arr):
        rasterio.features.rasterize(zip(geo, vals), out=arr, transform=tr5, dtype="uint8")

    cid = rasterio.features.rasterize(zip(com.geometry, range(1, len(com) + 1)), out_shape=shape,
                                      transform=tr5, fill=0, dtype="uint16")
    nC = len(com) + 1
    px = rs * rs / 1e4
    log(dep, "grille", rs, shape)

    # ---------------- recalcul (reference) : rasters + statut par identifiant
    O, ours_id = {}, {}
    for a, ya in (("2021", "2021"), ("2024", y2)):
        arr = np.zeros(shape, np.uint8)
        art = pd.read_parquet(out / f"artif_{a}.parquet", columns=["reference"])["reference"].to_numpy()
        pf = pq.ParquetFile(out / f"ocsge_{a}.parquet")
        off = 0
        for batch in pf.iter_batches(batch_size=B, columns=["geometry"]):
            gb = gpd.GeoDataFrame.from_arrow(batch).set_crs(2154, allow_override=True)
            burn(gb.geometry, np.where(art[off:off + len(gb)], 2, 1), arr)
            off += len(gb)
            del gb
        assert off == len(art)
        raw = glob.glob(str(out / f"x_{a}" / "**" / "OCCUPATION_SOL.gpkg"), recursive=True)[0]
        ids = pyogrio.read_dataframe(raw, columns=["id"], read_geometry=False)["id"].to_numpy()
        assert len(ids) == len(art), (len(ids), len(art))
        ours_id[a] = pd.Series(art, index=ids, name="ours")
        O[a] = arr
        gc.collect()
        log(dep, a, "recalcul rastérisé")

    # ---------------- couche IGN artificialisation
    I, vec = {}, {}
    for a, ya in (("2021", "2021"), ("2024", y2)):
        g = extraire(IGN / "artif" / f"OCS-GE_2-0_ARTIFICIALISATION_GPKG_LAMB93_{z3}_{ya}-01-01.7z", tmp / f"artif_{a}")
        n = pyogrio.read_info(g)["features"]
        arr = np.zeros(shape, np.uint8)
        parts = []
        for s in range(0, n, B):
            gb = pyogrio.read_dataframe(g, columns=["id", "code_cs", "code_us", "artif", "crit_seuil", "aire"],
                                        skip_features=s, max_features=B)
            st = (gb["artif"] == "artif").to_numpy()
            burn(gb.geometry, np.where(st, 2, 1), arr)
            parts.append(pd.DataFrame({"id": gb["id"].to_numpy(), "ign": st,
                                       "crit_seuil": gb["crit_seuil"].astype(str).str.lower().isin(["true", "1"]).to_numpy(),
                                       "aire": gb["aire"].astype(float).to_numpy()}))
            del gb
            gc.collect()
        I[a] = arr
        df = pd.concat(parts, ignore_index=True)
        vec[a] = df
        shutil.rmtree(tmp / f"artif_{a}", ignore_errors=True)
        log(dep, a, "IGN rastérisé", n, "polygones ; valeurs artif :", sorted(set(df.ign)))

    # ---------------- comparaison vectorielle par identifiant
    res = {"dep": dep, "periode": f"2021-{y2}", "pas_grille_m": rs}
    for a in ("2021", "2024"):
        df = vec[a].merge(ours_id[a].rename_axis("id").reset_index(), on="id", how="outer", indicator=True)
        res[f"vec_{a}_ids_ign_seuls"] = int((df._merge == "left_only").sum())
        res[f"vec_{a}_ids_recalc_seuls"] = int((df._merge == "right_only").sum())
        m = df[df._merge == "both"]
        ha = m.aire / 1e4
        res[f"vec_{a}_ign_ha"] = round(float(ha[m.ign].sum()), 1)
        res[f"vec_{a}_recalc_ha"] = round(float(ha[m.ours.astype(bool)].sum()), 1)
        res[f"vec_{a}_accord_artif_ha"] = round(float(ha[m.ign & m.ours.astype(bool)].sum()), 1)
        res[f"vec_{a}_ign_seul_ha"] = round(float(ha[m.ign & ~m.ours.astype(bool)].sum()), 1)
        res[f"vec_{a}_recalc_seul_ha"] = round(float(ha[~m.ign & m.ours.astype(bool)].sum()), 1)
        res[f"vec_{a}_desaccord_crit_seuil_ha"] = round(float(ha[(m.ign != m.ours.astype(bool)) & m.crit_seuil].sum()), 1)
    del vec, ours_id
    gc.collect()

    # ---------------- DIFF IGN (zan_evol)
    gz = extraire(IGN / "artif_diff" / f"OCS-GE-ARTIFICIALISATION_2-0_DIFF-2021-{y2}_GPKG_LAMB93_{z3}_*.7z", tmp / "diff")
    zan = pyogrio.read_dataframe(gz)
    zan = zan[zan.geometry.notna()].reset_index(drop=True)
    zan = zan.rename(columns={c: c.replace(f"_{y2}", "_2024") for c in zan.columns if c.endswith(f"_{y2}")})
    ZD = np.zeros(shape, np.uint8)
    burn(zan.geometry, np.where(zan.artificialisation > 0, 1, 2), ZD)
    res["vec_diff_artif_ha"] = round(float(zan.surface[zan.artificialisation > 0].sum() / 1e4), 2)
    res["vec_diff_desartif_ha"] = round(float(zan.surface[zan.artificialisation < 0].sum() / 1e4), 2)
    res["vec_diff_n"] = len(zan)

    # ---------------- patch correctif 2021
    gp = extraire(IGN / "patch" / f"OCS-GE_2-0_PATCHCORRECTIF_GPKG_LAMB93_{z3}_2021-01-01.7z", tmp / "patch")
    pa = pyogrio.read_dataframe(gp)
    pa = pa[pa.geometry.notna()].reset_index(drop=True)
    cs_new = pa.cs_corr.where(~pa.cs_corr.isin(["RAS", None, ""]), pa.code_cs)
    us_new = pa.us_corr.where(~pa.us_corr.isin(["RAS", None, ""]), pa.code_us)
    b0 = classer_brut(pa[["code_cs", "code_us"]], R).to_numpy()
    b1 = classer_brut(pd.DataFrame({"code_cs": cs_new, "code_us": us_new}), R).to_numpy()
    pa["ptype"] = np.select([~b0 & b1, b0 & ~b1], [2, 3], 1)
    P = np.zeros(shape, np.uint8)
    burn(pa.geometry, pa.ptype.to_numpy(), P)
    res["patch_n"] = len(pa)
    res["patch_ha"] = round(float(pa.area.sum() / 1e4), 1)
    res["patch_vers_artif_ha"] = round(float(pa.area[pa.ptype == 2].sum() / 1e4), 1)
    res["patch_vers_non_artif_ha"] = round(float(pa.area[pa.ptype == 3].sum() / 1e4), 1)

    # typologie vectorielle des polygones DIFF IGN
    zan["surf"] = zan.geometry.area
    zan["zid"] = np.arange(len(zan))
    for sens, pt, lab in ((-1, 3, "desartif"), (1, 2, "artif")):
        zz = zan[zan.artificialisation == sens]
        pp = pa[pa.ptype == pt][["geometry"]]
        inter = 0.0
        expl = pd.Series(0.0, index=zz.zid)
        if len(zz) and len(pp):
            ov = gpd.overlay(zz[["zid", "geometry"]], pp, how="intersection", keep_geom_type=True)
            if len(ov):
                expl = ov.assign(a=ov.area).groupby("zid").a.sum().reindex(zz.zid, fill_value=0.0)
                inter = float(expl.sum())
        rest = zz.set_index("zid").surf - expl.clip(upper=zz.set_index("zid").surf)
        zi = zz.set_index("zid")
        same_cs, same_us = zi.cs_2021 == zi.cs_2024, zi.us_2021 == zi.us_2024
        res[f"diff_{lab}_patch_ha"] = round(inter / 1e4, 2)
        res[f"diff_{lab}_cs_change_us_identique_ha"] = round(float(rest[~same_cs & same_us].sum() / 1e4), 2)
        res[f"diff_{lab}_us_change_ha"] = round(float(rest[~same_us].sum() / 1e4), 2)
        res[f"diff_{lab}_codes_identiques_ha"] = round(float(rest[same_cs & same_us].sum() / 1e4), 2)
    shutil.rmtree(tmp, ignore_errors=True)
    del zan, pa
    gc.collect()

    # ---------------- statistiques raster par commune
    def bc(mask, w=1.0):
        return np.bincount(cid[mask], minlength=nC) * px * w

    o21, o24, i21, i24 = O["2021"], O["2024"], I["2021"], I["2024"]
    G = (o21 == 1) & (o24 == 2)
    Rt = (o21 == 2) & (o24 == 1)
    cols = {
        "recalc_stock_2021": bc(o21 == 2), "ign_stock_2021": bc(i21 == 2),
        "recalc_stock_2024": bc(o24 == 2), "ign_stock_2024": bc(i24 == 2),
        "recalc_artif_ha_an": bc(G, 1 / NY), "ign_diff_artif_ha_an": bc(ZD == 1, 1 / NY),
        "recalc_desartif_ha_an": bc(Rt, 1 / NY), "ign_diff_desartif_ha_an": bc(ZD == 2, 1 / NY),
        "ign_millesimes_artif_ha_an": bc((i21 == 1) & (i24 == 2), 1 / NY),
        "ign_millesimes_desartif_ha_an": bc((i21 == 2) & (i24 == 1), 1 / NY),
        "recalc_artif_patch_ha_an": bc(G & (P == 2), 1 / NY),
        "recalc_desartif_patch_ha_an": bc(Rt & (P == 3), 1 / NY),
        "recalc_desartif_dans_patch_ha_an": bc(Rt & (P > 0), 1 / NY),
        "ign_diff_artif_patch_ha_an": bc((ZD == 1) & (P == 2), 1 / NY),
        "ign_diff_desartif_patch_ha_an": bc((ZD == 2) & (P == 3), 1 / NY),
        "recalc_desartif_hors_diff_ign_ha_an": bc(Rt & (ZD != 2), 1 / NY),
        "recalc_artif_hors_diff_ign_ha_an": bc(G & (ZD != 1), 1 / NY),
        "desaccord_stock_2021_ha": bc((o21 > 0) & (i21 > 0) & (o21 != i21)),
    }
    del O, I, P, ZD, G, Rt
    gc.collect()
    tab = pd.DataFrame(cols)
    tab.insert(0, "insee", ["_hors"] + list(com.insee))
    tab.insert(1, "nom", [""] + list(com.nom))
    tab = tab.iloc[1:].reset_index(drop=True)

    # contrôle vs data.json
    dj = json.load(open(ROOT / "web" / dep / "data.json"))
    ind = dj["indicateurs"]
    tab["datajson_stock_2021"] = [ind.get(c, {}).get("stock", {}).get("reference", {}).get("2021", np.nan) for c in tab.insee]
    tab["datajson_artif_ha_an"] = [ind.get(c, {}).get("flux_brut", {}).get("reference", {}).get("artif", np.nan) for c in tab.insee]
    tab.insert(0, "dep", dep)
    tab.round(3).to_csv(OUT / f"{dep}_communes.csv", index=False)
    tot = tab.drop(columns=["dep", "insee", "nom"]).sum()
    res.update({k: round(float(v), 2) for k, v in tot.items()})
    res["datajson_dep"] = {"stock": dj["departement"]["stock"]["reference"], "flux_brut": dj["departement"]["flux_brut"]["reference"]}
    json.dump(res, open(OUT / f"{dep}_dep.json", "w"), indent=1, ensure_ascii=False)
    log(dep, "fini", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
