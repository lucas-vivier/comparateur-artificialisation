"""Millésime OCS GE 2021 corrigé : application du patch correctif IGN (PATCHCORRECTIF 2021).

Le patch donne des polygones dont la couverture (cs_corr) et/ou l'usage (us_corr) ont été corrigés
(« RAS » = inchangé). Quand decoup_geo = 1, le polygone corrigé est un morceau redécoupé d'un
polygone d'origine. Méthode : on retire de la couche 2021 la surface couverte par le patch, puis on
ajoute les polygones du patch avec leurs codes corrigés. La topologie est recalculée.

Sortie : data/processed/<dep>/ocsge_2021c.parquet et topo_2021c.npz
Usage : python scripts/corriger_2021.py 94
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import py7zr
import shapely

from occsol.paths import PROCESSED, RAW

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_dep import communes, log  # noqa: E402

PATCH = RAW / "ign_artif" / "patch"


def lire_patch(dep):
    arch = PATCH / f"OCS-GE_2-0_PATCHCORRECTIF_GPKG_LAMB93_D0{dep}_2021-01-01.7z"
    with tempfile.TemporaryDirectory() as tmp, py7zr.SevenZipFile(arch) as z:
        z.extractall(tmp)
        f = next(Path(tmp).rglob("*.gpkg"))
        p = gpd.read_file(f, columns=["code_cs", "code_us", "cs_corr", "us_corr", "decoup_geo"], engine="pyogrio")
    ok = lambda c: c.notna() & ~c.isin(["RAS", "NC", ""])  # noqa: E731
    p["cs_new"] = p.cs_corr.where(ok(p.cs_corr), p.code_cs)
    p["us_new"] = p.us_corr.where(ok(p.us_corr), p.code_us)
    p = p.explode(index_parts=False).reset_index(drop=True)
    return p.set_crs(2154, allow_override=True)


def main(dep):
    out = PROCESSED / dep
    g = gpd.read_parquet(out / "ocsge_2021.parquet")
    p = lire_patch(dep)
    log(dep, "patch", len(p), "polygones ;", round(p.area.sum() / 1e4, 1), "ha ; couche 2021", len(g))
    tree = g.sindex
    gi, pj = tree.query(p.geometry, predicate="intersects")  # renvoie (indices patch, indices couche)
    pi_, gj = gi, pj
    touches = pd.DataFrame({"g": gj, "p": pi_})
    pg = p.geometry.to_numpy()
    nouv = []
    for k, grp in touches.groupby("g"):
        geom = g.geometry.iat[k]
        reste = shapely.difference(geom, shapely.union_all(pg[grp.p.to_numpy()]))
        nouv.append(reste)
    aff = np.array(sorted(touches.g.unique()))
    restes = gpd.GeoDataFrame({"code_cs": g.code_cs.to_numpy()[aff], "code_us": g.code_us.to_numpy()[aff]},
                              geometry=nouv, crs=2154).explode(index_parts=False)
    restes = restes[restes.geom_type.isin(["Polygon"]) & (restes.area > 1)]
    garde = np.ones(len(g), bool)
    garde[aff] = False
    add = gpd.GeoDataFrame({"code_cs": p.cs_new, "code_us": p.us_new}, geometry=p.geometry, crs=2154)
    c = pd.concat([g[garde], restes, add], ignore_index=True)
    c = gpd.GeoDataFrame(c, geometry="geometry", crs=2154)
    a0, a1 = g.area.sum() / 1e4, c.area.sum() / 1e4
    log(dep, "couche corrigée", len(c), "polygones ; surface", round(a1, 1), "ha contre", round(a0, 1), f"({100 * (a1 - a0) / a0:+.3f} %)")
    from occsol.nomenclature import adjacence
    i, j = adjacence(c.geometry.values)
    np.savez_compressed(out / "topo_2021c.npz", i=i, j=j, bord=np.zeros(len(c), bool))
    c.to_parquet(out / "ocsge_2021c.parquet")
    log(dep, "ocsge_2021c ok")


if __name__ == "__main__":
    main(sys.argv[1])
