"""Piste B.2/B.3 — Carroyage CONSOENAF (Cerema, 1 km, EPSG:3035) vs flux OCS GE recalculés (règle de référence).

Usage (sous verrou) : flock /home/claude/occsol/.heavy.lock python scripts/piste_B_carroyage.py 94
Source carroyage : data.gouv.fr, jeu « CONSOENAF 2011-2025 » (Cerema), ressource conso_carroyage.gpkg
  https://static.data.gouv.fr/resources/consommation-despaces-naturels-agricoles-et-forestiers-du-1er-janvier-2011-au-1er-janvier-2025/20260511-111136/conso-carroyage.gpkg
Méthode :
- OCS GE : statut artificialisé (variante reference, déjà calculée dans artif_<a>.parquet) rastérisé en Lambert-93
  (5 m ; 10 m pour les grands départements, comme pipeline_dep.py), polygones lus par lots de 100 000.
  Pixel « devenu artificialisé » = non artif 2021 et artif au second millésime (2024 ; 2025 pour le Nord).
  On note aussi le code_us du second millésime (destination) et du 2021 sur ces pixels.
- Chaque pixel est rattaché au carreau 1 km (EPSG:3035) qui contient son centre.
- FF : somme des flux annuels sur la même période (94 : 2021-2024, 3 ans ; 59 : 2021-2025, 4 ans), en ha.
- Corrélations sur les carreaux entièrement inclus dans le département (part de surface >= 0,99).
Sorties : outputs/tables/piste_B_carreaux_<dep>.csv, piste_B_usages_flux_<dep>.csv, piste_B_correlation_<dep>.csv
"""
import gc
import math
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyogrio
import rasterio.features
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box

from occsol.paths import CONFIG, PROCESSED, RAW, ROOT

dep = sys.argv[1]
Y2 = {"59": "2025"}.get(dep, "2024")
NY = int(Y2) - 2021
CARR = RAW / "cerema" / "carroyage" / "conso_carroyage.gpkg"
OUT = ROOT / "outputs" / "tables"
out = PROCESSED / dep

com = gpd.read_file(RAW / "communes" / f"communes_{dep}.geojson").to_crs(2154)
depg = com.geometry.union_all()
x0, y0, x1, y1 = com.total_bounds
rs = 5.0 if (x1 - x0) * (y1 - y0) / 25 < 1.5e8 else (10.0 if (x1 - x0) * (y1 - y0) / 100 < 6e7 else 15.0)
W, H = int(math.ceil((x1 - x0) / rs)), int(math.ceil((y1 - y0) / rs))
tr = from_origin(x0, y1, rs, rs)
px = rs * rs / 1e4
print(dep, "grille", rs, W, H, flush=True)

nom = pd.read_csv(CONFIG / "nomenclature_ocsge.csv", sep=";")
US = list(nom[nom.CODE.str.startswith("US")].CODE)
usi = {c: i + 1 for i, c in enumerate(US)}

A, U = {}, {}
for a in ["2021", "2024"]:
    art = pq.read_table(out / f"artif_{a}.parquet", columns=["reference"]).column(0).to_numpy(zero_copy_only=False)
    A[a] = np.zeros((H, W), np.uint8)
    U[a] = np.zeros((H, W), np.uint8)
    off = 0
    for b in pq.ParquetFile(out / f"ocsge_{a}.parquet").iter_batches(batch_size=100000, columns=["code_us", "geometry"]):
        gb = gpd.GeoDataFrame.from_arrow(b).set_crs(2154, allow_override=True)
        n = len(gb)
        rasterio.features.rasterize(zip(gb.geometry, np.where(art[off:off + n], 2, 1)), out=A[a], transform=tr, dtype="uint8")
        rasterio.features.rasterize(zip(gb.geometry, gb.code_us.map(usi).fillna(0).astype(int)), out=U[a], transform=tr, dtype="uint8")
        off += n
        del gb, b
        gc.collect()
    assert off == len(art)
    print(dep, a, "rastérisé", flush=True)
inside = rasterio.features.rasterize([(depg, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8") == 1
new = (A["2021"] == 1) & (A["2024"] == 2) & inside
ret = (A["2021"] == 2) & (A["2024"] == 1) & inside
r, c = np.nonzero(new)
us_new24, us_new21 = U["2024"][r, c], U["2021"][r, c]
rr, cr = np.nonzero(ret)
us_ret21 = U["2021"][rr, cr]
del A, U, inside
gc.collect()
print(dep, "pixels devenus artif", len(r), "->", round(len(r) * px / NY, 2), "ha/an", flush=True)

# --- décomposition des flux OCS GE par usage (destination au second millésime, et usage 2021)
lab = dict(zip(nom.CODE, nom.LIBELLE.str.strip()))
rows = []
tot = len(r) * px
for k, code in enumerate(US, start=1):
    v24 = (us_new24 == k).sum() * px
    v21 = (us_new21 == k).sum() * px
    vr = (us_ret21 == k).sum() * px
    rows.append({"dep": dep, "code_us": code, "libelle": lab.get(code, ""), "devenu_artif_ha_usage_fin": round(v24, 2),
                 "part_usage_fin": round(v24 / tot, 4) if tot else None, "devenu_artif_ha_usage_2021": round(v21, 2),
                 "desartif_ha_usage_2021": round(vr, 2)})
rows.append({"dep": dep, "code_us": "TOTAL", "libelle": f"periode 2021-{Y2} ({NY} ans), grille {rs:g} m",
             "devenu_artif_ha_usage_fin": round(tot, 2), "part_usage_fin": 1.0,
             "devenu_artif_ha_usage_2021": round(tot, 2), "desartif_ha_usage_2021": round(len(rr) * px, 2)})
pd.DataFrame(rows).to_csv(OUT / f"piste_B_usages_flux_{dep}.csv", index=False)

# --- rattachement aux carreaux 1 km EPSG:3035
t = Transformer.from_crs(2154, 3035, always_xy=True)
X = x0 + (c + 0.5) * rs
Y = y1 - (r + 0.5) * rs
ex, ny_ = t.transform(X, Y)
cid = pd.Series((np.floor(np.asarray(ny_) / 1000).astype(int)).astype(str))
cid = "1kmN" + cid + "E" + pd.Series(np.floor(np.asarray(ex) / 1000).astype(int).astype(str))
cat = np.select([us_new24 == usi["US4.1.1"], us_new24 == usi["US4.1.2"],
                 np.isin(us_new24, [usi[u] for u in ("US4.1.3", "US4.1.4", "US4.1.5")])], ["routes", "fer", "autres_transports"], "autre")
oc = pd.DataFrame({"idcarreau": cid, "cat": cat}).groupby(["idcarreau", "cat"]).size().unstack(fill_value=0) * px
oc = oc.reindex(columns=["routes", "fer", "autres_transports", "autre"], fill_value=0)
oc["ocs_brut_ha"] = oc.sum(axis=1)
oc = oc.rename(columns={k: f"ocs_{k}_ha" for k in ["routes", "fer", "autres_transports", "autre"]})

# carreaux couvrant le département + part de surface incluse
bx = gpd.GeoSeries([box(*com.total_bounds)], crs=2154).to_crs(3035).total_bounds
E = np.arange(math.floor(bx[0] / 1000), math.ceil(bx[2] / 1000))
N = np.arange(math.floor(bx[1] / 1000), math.ceil(bx[3] / 1000))
ee, nn = np.meshgrid(E, N)
ee, nn = ee.ravel(), nn.ravel()
g = gpd.GeoDataFrame({"idcarreau": [f"1kmN{n}E{e}" for e, n in zip(ee, nn)]},
                     geometry=[box(e * 1000, n * 1000, e * 1000 + 1000, n * 1000 + 1000) for e, n in zip(ee, nn)], crs=3035).to_crs(2154)
g = g[g.intersects(depg)].copy()
g["part_dans_dep"] = g.geometry.intersection(depg).area / g.geometry.area
cells = g[["idcarreau", "part_dans_dep"]].set_index("idcarreau")

ans = ["21", "22", "23", "24"][:NY]
dest = ["hab", "act", "mix", "rou", "fer", "inc"]
fcols = [f"naf{a}art{int(a)+1}" for a in ans] + [f"art{a}{d}{int(a)+1}" for a in ans for d in dest]
ff = pyogrio.read_dataframe(CARR, columns=["idcarreau"] + fcols, bbox=tuple(bx), read_geometry=False)
ffd = pd.DataFrame({"idcarreau": ff.idcarreau, "ff_total_ha": sum(ff[f"naf{a}art{int(a)+1}"] for a in ans) / 1e4})
for d in dest:
    ffd[f"ff_{d}_ha"] = sum(ff[f"art{a}{d}{int(a)+1}"] for a in ans) / 1e4
ffd = ffd.set_index("idcarreau")
print(dep, "carreaux FF lus (bbox)", len(ff), "dont dans emprise", ffd.index.isin(cells.index).sum(), flush=True)
m = cells.join(oc, how="left").join(ffd, how="left").fillna(0)
m["present_fichier_ff"] = cells.index.isin(ffd.index)
m.round(4).to_csv(OUT / f"piste_B_carreaux_{dep}.csv")

# --- corrélations (carreaux entièrement inclus)
res = []
for nomsel, sel in [("inclus_>=0.99", m.part_dans_dep >= 0.99), ("tous_intersectant", m.part_dans_dep > 0)]:
    s = m[sel]
    for (ca, cb) in [("ocs_brut_ha", "ff_total_ha"), ("ocs_routes_ha", "ff_rou_ha")]:
        nz = (s[ca] > 0) | (s[cb] > 0)
        res.append({"dep": dep, "periode": f"2021-{Y2}", "selection": nomsel, "x": ca, "y": cb, "n_carreaux": int(sel.sum()),
                    "n_non_nuls": int(nz.sum()), "somme_x_ha": round(s[ca].sum(), 2), "somme_y_ha": round(s[cb].sum(), 2),
                    "pearson": round(s[ca].corr(s[cb]), 3), "spearman": round(s[ca].corr(s[cb], method="spearman"), 3),
                    "pearson_non_nuls": round(s[nz][ca].corr(s[nz][cb]), 3),
                    "n_ocs>0_ff=0": int(((s[ca] > 0) & (s[cb] == 0)).sum()), "n_ff>0_ocs=0": int(((s[cb] > 0) & (s[ca] == 0)).sum())})
cr = pd.DataFrame(res)
cr.to_csv(OUT / f"piste_B_correlation_{dep}.csv", index=False)
print(cr.to_string())
print(pd.DataFrame(rows).sort_values("devenu_artif_ha_usage_fin", ascending=False).head(10).to_string())
