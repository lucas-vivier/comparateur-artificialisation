"""Piste C — décomposition des écarts OCS GE (artificialisé, règle officielle recalculée) / base régionale
(MOS IDF 79 postes ; OCS2D Hauts-de-France, classement NAF / non-NAF), millésime 2021.

Usage (un département à la fois, sous verrou) :
    flock /home/claude/occsol/.heavy.lock python scripts/piste_C_ecarts.py 94

Méthode :
  * grille Lambert-93 identique à pipeline_dep.py (emprise des communes, pas 5/10/15 m, mêmes règles
    de rastérisation et même ordre d'écriture) -> l'accord pixel « reference » doit retrouver
    data.json (departement.mos.accord_2021) ;
  * on rastérise l'INDICE du polygone (OCS GE 2021 et base régionale 2021), puis on compte les pixels
    par couple (polygone OCS GE, polygone régional) : table d'intersections au pixel ;
  * chaque couple porte les attributs OCS GE (CS, US, statut brut, statut final par variante,
    bascule au seuillage) et régionaux (poste MOS ou enaf/urba OCS2D) ;
  * les désaccords sont classés en familles (voir FAMILLES ci-dessous, ordre de priorité).
Sorties : outputs/tables/piste_C/<dep>_matrice.csv, <dep>_familles.csv, <dep>_variantes.csv, <dep>.json
"""
from __future__ import annotations

import gc
import json
import math
import resource
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyogrio
import rasterio.features
import shapely
from rasterio.transform import from_origin

from occsol import mos
from occsol.nomenclature import Regle, classer_brut
from occsol.paths import PROCESSED, RAW, ROOT

OUT = ROOT / "outputs" / "tables" / "piste_C"
HDF = {"02", "59", "60", "62", "80"}
ENAF_HDF = RAW / "hdf" / "ocs2d_enaf_2024_v2.gpkg"
VARIANTES = ["reference", "sans_herbace", "seuil_0", "seuil_1000", "seuil_5000"]
B = 100_000

# --- familles (priorité dans l'ordre) -------------------------------------------------------
# D1 = OCS GE artificialisé / base régionale ENAF (NAF) ; D2 = OCS GE non artificialisé / base régionale urbaine
US_CHANTIER_INFRA = ("US1.3", "US4.1.1", "US4.1.2", "US4.1.3", "US4.1.4", "US4.1.5", "US4.2", "US4.3", "US6.1")
MOS_EV = set(range(13, 16)) | set(range(17, 28))          # espaces verts, sport, loisirs, cimetières, vacants (sauf 16)
MOS_JARD = {16, 28, 29, 30}                              # jardins de l'habitat, habitat individuel / rural
MOS_CHI = set(range(46, 55)) | set(range(73, 80))        # ressources (dont extraction, déchets), transports, chantiers
SLIVER_HA = 0.25   # intersection < 2 500 m² ...
SLIVER_PART = 0.25  # ... et < 25 % de chacun des deux polygones -> décalage de contours / généralisation


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def grille(com):
    x0, y0, x1, y1 = com.total_bounds
    rs = 5.0 if (x1 - x0) * (y1 - y0) / 25 < 1.5e8 else (10.0 if (x1 - x0) * (y1 - y0) / 100 < 6e7 else 15.0)
    W, H = int(math.ceil((x1 - x0) / rs)), int(math.ceil((y1 - y0) / rs))
    return rs, from_origin(x0, y1, rs, rs), (H, W)


def main(dep):
    OUT.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / dep
    com = gpd.read_file(RAW / "communes" / f"communes_{dep}.geojson").to_crs(2154)
    rs, tr, shape = grille(com)
    px = rs * rs / 1e4
    cid = rasterio.features.rasterize(zip(com.geometry, range(1, len(com) + 1)), out_shape=shape, transform=tr,
                                      fill=0, dtype="uint16") > 0
    log(dep, "grille", rs, shape)

    # ---------------- OCS GE 2021 : indice de polygone + attributs
    ocs = np.zeros(shape, np.int32)
    pf = pq.ParquetFile(out / "ocsge_2021.parquet")
    att, off = [], 0
    for batch in pf.iter_batches(batch_size=B):
        geo = shapely.from_wkb(batch.column("geometry").to_numpy(zero_copy_only=False))
        rasterio.features.rasterize(zip(geo, range(off + 1, off + 1 + len(geo))), out=ocs, transform=tr, dtype="int32")
        att.append(pd.DataFrame({"cs": batch.column("code_cs").to_pylist(), "us": batch.column("code_us").to_pylist(),
                                 "aire_m2": shapely.area(geo)}))
        off += len(geo)
        del geo, batch
        gc.collect()
    A = pd.concat(att, ignore_index=True)
    del att
    art = pd.read_parquet(out / "artif_2021.parquet")
    assert len(art) == len(A), (len(art), len(A))
    for v in VARIANTES:
        A[v] = art[v].to_numpy()
    A["brut"] = classer_brut(A.rename(columns={"cs": "code_cs", "us": "code_us"}), Regle.reference()).to_numpy()
    A["bascule"] = A.brut != A.reference
    A["herbace_artif"] = A.cs.isin(["CS2.2.1", "CS2.2.2"]) & A.brut
    del art
    log(dep, "OCS GE", len(A))

    # ---------------- base régionale 2021 : indice de polygone + attributs
    reg = np.zeros(shape, np.int32)
    if dep in HDF:
        bb = tuple(com.total_bounds)
        ntot = pyogrio.read_info(ENAF_HDF, layer="ocs2d_enaf_opendata")["features"]
        att, off = [], 0
        for o in range(0, ntot, 100000):  # même ordre que pipeline_dep.py, morceaux plus petits (mémoire)
            c = gpd.read_file(ENAF_HDF, layer="ocs2d_enaf_opendata", bbox=bb, engine="pyogrio", skip_features=o,
                              max_features=100000, columns=["enaf_2021", "urba_2021", "urba_2024", "cs21", "us21"])
            if c.empty:
                continue
            c = c[c.urba_2021.isin(["NAF", "Non-NAF"]) & c.urba_2024.isin(["NAF", "Non-NAF"])]
            rasterio.features.rasterize(zip(c.geometry, range(off + 1, off + 1 + len(c))), out=reg, transform=tr, dtype="int32")
            att.append(pd.DataFrame({"r_classe": c.enaf_2021.to_numpy(), "r_urbain": (c.urba_2021 == "Non-NAF").to_numpy(),
                                     "r_cs": c.cs21.to_numpy(), "r_us": c.us21.to_numpy()}))
            off += len(c)
            del c
            gc.collect()
        R = pd.concat(att, ignore_index=True)
    else:
        nm = mos.nomenclature().set_index("code")
        f = RAW / "mos" / f"mos_idf_{dep}_2021_2025.parquet"
        att, off = [], 0
        for batch in pq.ParquetFile(f).iter_batches(batch_size=B, columns=["geometry", "mos2021"]):
            geo = shapely.from_wkb(batch.column("geometry").to_numpy(zero_copy_only=False))
            rasterio.features.rasterize(zip(geo, range(off + 1, off + 1 + len(geo))), out=reg, transform=tr, dtype="int32")
            p = batch.column("mos2021").to_numpy()
            att.append(pd.DataFrame({"r_poste": p}))
            off += len(geo)
            del geo, batch
            gc.collect()
        R = pd.concat(att, ignore_index=True)
        R["r_urbain"] = R.r_poste.map(nm.enaf).to_numpy() == 0
        R["r_classe"] = R.r_poste.map(nm.libelle12).to_numpy()
    log(dep, "régional", len(R))

    # ---------------- table d'intersections au pixel
    nR = len(R) + 1
    parts = []
    ocs_sans_reg = 0
    step = max(1, 4_000_000 // shape[1])
    for r0 in range(0, shape[0], step):
        o = ocs[r0:r0 + step]
        g = reg[r0:r0 + step]
        m = cid[r0:r0 + step] & (o > 0)
        ocs_sans_reg += int((m & (g == 0)).sum())
        m &= g > 0
        k = o[m].astype(np.int64) * nR + g[m]
        u, n = np.unique(k, return_counts=True)
        parts.append(pd.DataFrame({"k": u, "n": n}))
    del ocs, reg, cid
    gc.collect()
    P = pd.concat(parts).groupby("k", as_index=False).n.sum()
    P["oi"] = (P.k // nR - 1).astype(np.int64)
    P["ri"] = (P.k % nR - 1).astype(np.int64)
    P = P.drop(columns="k")
    log(dep, "couples", len(P))
    no = np.bincount(P.oi, weights=P.n, minlength=len(A))
    nr = np.bincount(P.ri, weights=P.n, minlength=len(R))
    P["sliver"] = ((P.n * px < SLIVER_HA) & (P.n < SLIVER_PART * no[P.oi]) & (P.n < SLIVER_PART * nr[P.ri])).to_numpy()
    for c in ["cs", "us", "brut", "bascule", "herbace_artif"] + VARIANTES:
        P[c] = A[c].to_numpy()[P.oi]
    for c in R.columns:
        P[c] = R[c].to_numpy()[P.ri]
    P["ha"] = P.n * px

    # ---------------- familles
    ref, urb = P.reference.to_numpy(), P.r_urbain.to_numpy()
    sens = np.select([ref & ~urb, ~ref & urb, ref & urb], ["D1_ocs_artif_reg_enaf", "D2_ocs_non_artif_reg_urbain", "accord_artif"],
                     "accord_non_artif")
    P["sens"] = sens
    us = P.us.astype(str)
    c_ocs = us.isin(US_CHANTIER_INFRA).to_numpy()
    seuil = (P.bascule | P.sliver).to_numpy()
    d_ocs = ((P.cs == "CS1.1.1.1") | us.isin(["US5", "US235"])).to_numpy()
    if dep in HDF:
        rus = P.r_us.astype(str)
        c_reg = (P.r_classe == "Infrastructure").to_numpy() | rus.str.startswith(("US6.1", "US1.3")).to_numpy()
        d_reg = (P.r_classe == "Habitat").to_numpy()
        a_reg = P.r_classe.isin(["Activité", "Urbanisé autre"]).to_numpy() & P.cs.astype(str).str.startswith("CS2").to_numpy()
    else:
        po = P.r_poste.to_numpy()
        c_reg, d_reg, a_reg = np.isin(po, list(MOS_CHI)), np.isin(po, list(MOS_JARD)), np.isin(po, list(MOS_EV))
    d1 = np.select([seuil, P.herbace_artif.to_numpy(), c_ocs, d_ocs],
                   ["b_seuil_generalisation", "a_herbace_espaces_verts", "c_chantiers_carrieres_infra", "d_jardins_bati_diffus"],
                   "e_residu")
    d2 = np.select([seuil, c_reg | c_ocs, a_reg, d_reg],
                   ["b_seuil_generalisation", "c_chantiers_carrieres_infra", "a_herbace_espaces_verts", "d_jardins_bati_diffus"],
                   "e_residu")
    P["famille"] = np.where(sens == "D1_ocs_artif_reg_enaf", d1, np.where(sens == "D2_ocs_non_artif_reg_urbain", d2, ""))
    P["detail_seuil"] = np.where(P.bascule, "bascule_seuillage", np.where(P.sliver, "contour", ""))

    # ---------------- sorties
    rcols = ["r_poste", "r_classe"] if dep not in HDF else ["r_classe", "r_cs", "r_us"]
    mat = (P[P.sens.str.startswith("D")].groupby(["sens", "famille", "detail_seuil", "cs", "us"] + rcols, dropna=False)
           .ha.sum().round(2).reset_index().sort_values("ha", ascending=False))
    mat.insert(0, "dep", dep)
    mat.to_csv(OUT / f"{dep}_matrice.csv", index=False)
    fam = P[P.sens.str.startswith("D")].groupby(["sens", "famille"]).ha.sum().reset_index()
    fam.insert(0, "dep", dep)
    fam.to_csv(OUT / f"{dep}_familles.csv", index=False)
    tot = P.n.sum()
    var = []
    for v in VARIANTES:
        a = P[v].to_numpy()
        var.append({"dep": dep, "variante": v, "accord_pixel": float(P.n[a == urb].sum() / tot),
                    "ocs_seul_ha": float(P.ha[a & ~urb].sum()), "reg_seul_ha": float(P.ha[~a & urb].sum()),
                    "ocs_artif_ha": float(P.ha[a].sum()), "reg_urbain_ha": float(P.ha[urb].sum())})
    pd.DataFrame(var).to_csv(OUT / f"{dep}_variantes.csv", index=False)
    meta = {"dep": dep, "pas_m": rs, "surface_commune_ocs_ha": float(tot * px + ocs_sans_reg * px),
            "ocs_sans_regional_ha": ocs_sans_reg * px, "n_couples": int(len(P)),
            "maxrss_mo": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    (OUT / f"{dep}.json").write_text(json.dumps(meta))
    log(dep, "fini", var[0], meta)


if __name__ == "__main__":
    main(sys.argv[1])
