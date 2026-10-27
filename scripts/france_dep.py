"""Département sans base régionale : OCS GE (deux derniers millésimes) face aux Fichiers fonciers -> web/<dep>/.

Chaîne autonome, reprenable, qui libère le disque à la fin :
  1. catalogue Géoplateforme -> deux derniers millésimes OCS GE 2.0 (y1, y2) et patch correctif de y1 s'il existe ;
  2. topologie, classement artificialisé (règle officielle et variantes), y1 corrigé si patch ;
  3. cartes légères (≈ 4 Mpx), statistiques par commune, Fichiers fonciers alignés exactement sur y1-y2 ;
  4. rythmes par destination (OCS GE : usage y2 des surfaces devenues artificialisées ; Fichiers fonciers : destination déclarée).

Les clés internes gardent les noms de fichiers du comparateur ("2021" = y1, "2024" = y2) ; les vraies années sont dans
sources.ocsge_annees et sources.ff_periode.

Usage : python scripts/france_dep.py 32 [--garder]
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import py7zr
import pyarrow.parquet as pq
import rasterio.features
import requests
import shapely
from PIL import Image
from pyproj import Transformer
from rasterio.transform import from_origin

from occsol import territoires
from occsol.nomenclature import adjacence, classer_brut, seuiller
from occsol.paths import CONFIG, PROCESSED, RAW, ROOT

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_dep import ART, BASE, EV, H, regles, save_png  # noqa: E402
from decomposer import DEST, DEST_LIB, dest_us  # noqa: E402

GEOPF = "https://data.geopf.fr/telechargement"
B = 20_000
MAXPX = 4e6


def log(dep, *a):
    print(time.strftime("%H:%M:%S"), dep, *a, flush=True)


def zone(dep):
    return f"D{dep.zfill(3)}"


def catalogue(dep, res="OCSGE"):
    r = requests.get(f"{GEOPF}/resource/{res}", params={"zone": zone(dep), "limit": 50}, timeout=120)
    r.raise_for_status()
    return sorted(set(re.findall(r"OCS-GE_2-0[_A-Z-]*_GPKG_LAMB93_" + zone(dep) + r"_\d{4}-\d{2}-\d{2}", r.text)))


def telecharger(res, nom, dest: Path):
    f = dest / f"{nom}.7z"
    if f.exists() and f.stat().st_size > 0:
        return f
    for k in range(6):
        try:
            with requests.get(f"{GEOPF}/download/{res}/{nom}/{nom}.7z", stream=True, timeout=900) as r:
                r.raise_for_status()
                tmp = f.with_suffix(".part")
                with open(tmp, "wb") as h:
                    for c in r.iter_content(1 << 20):
                        h.write(c)
                tmp.rename(f)
            return f
        except Exception as e:  # noqa: BLE001
            print("retry", k, nom, e, flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError(f"téléchargement impossible : {nom}")


def communes(dep):
    for k in range(40):
        try:
            com = territoires.communes(dep)
            break
        except Exception as e:  # noqa: BLE001
            print("retry communes", k, e, flush=True)
            time.sleep(5)
    else:
        raise RuntimeError("contours communaux indisponibles")
    return com[["insee", "nom", "geometry"]].reset_index(drop=True)


# ------------------------------------------------------------------ 1-2. préparation et classement
def preparer(dep, out, raw):
    noms = [n for n in catalogue(dep) if "__GPKG" in n]
    ans = sorted({n[-10:-6] for n in noms})
    y1, y2 = ans[-2], ans[-1]
    patch = [n for n in catalogue(dep) if "PATCHCORRECTIF" in n and n.endswith(f"{y1}-01-01")]
    meta = {"y1": y1, "y2": y2, "millesimes": ans, "patch": bool(patch)}
    (out / "meta.json").write_text(json.dumps(meta))
    for slot, y in [("2021", y1), ("2024", y2)]:
        if (out / f"ocsge_{slot}.parquet").exists():
            continue
        nom = f"OCS-GE_2-0__GPKG_LAMB93_{zone(dep)}_{y}-01-01"
        arch = telecharger("OCSGE", nom, raw)
        tmp = out / f"x_{slot}"
        with py7zr.SevenZipFile(arch) as z:
            z.extract(tmp, targets=[n for n in z.getnames() if n.endswith("OCCUPATION_SOL.gpkg")])
        g = gpd.read_file(next(tmp.rglob("OCCUPATION_SOL.gpkg")), columns=["code_cs", "code_us"], engine="pyogrio")
        g = g.explode(index_parts=False).reset_index(drop=True)
        i, j = adjacence(g.geometry.values)
        np.savez_compressed(out / f"topo_{slot}.npz", i=i, j=j)
        g.to_parquet(out / f"ocsge_{slot}.parquet")
        shutil.rmtree(tmp, ignore_errors=True)
        arch.unlink()
        log(dep, y, len(g), "polygones")
        del g
        gc.collect()
    if patch and not (out / "ocsge_2021c.parquet").exists():
        corriger(dep, out, raw, patch[0])
    return meta


def corriger(dep, out, raw, nom):
    arch = telecharger("OCSGE", nom, raw)
    tmp = out / "x_patch"
    with py7zr.SevenZipFile(arch) as z:
        z.extractall(tmp)
    p = gpd.read_file(next(tmp.rglob("*.gpkg")), columns=["code_cs", "code_us", "cs_corr", "us_corr"], engine="pyogrio")
    shutil.rmtree(tmp, ignore_errors=True)
    arch.unlink()
    ok = lambda c: c.notna() & ~c.isin(["RAS", "NC", ""])  # noqa: E731
    p["code_cs"] = p.cs_corr.where(ok(p.cs_corr), p.code_cs)
    p["code_us"] = p.us_corr.where(ok(p.us_corr), p.code_us)
    p = p[["code_cs", "code_us", "geometry"]].explode(index_parts=False).reset_index(drop=True).set_crs(2154, allow_override=True)
    g = gpd.read_parquet(out / "ocsge_2021.parquet")
    pi, gi = g.sindex.query(p.geometry, predicate="intersects")
    pg = p.geometry.to_numpy()
    t = pd.DataFrame({"g": gi, "p": pi})
    aff = np.array(sorted(t.g.unique()), dtype=int)
    restes = [shapely.difference(g.geometry.iat[k], shapely.union_all(pg[grp.p.to_numpy()])) for k, grp in t.groupby("g")]
    r = gpd.GeoDataFrame({"code_cs": g.code_cs.to_numpy()[aff], "code_us": g.code_us.to_numpy()[aff]}, geometry=restes, crs=2154)
    r = r.explode(index_parts=False)
    r = r[(r.geom_type == "Polygon") & (r.area > 1)]
    garde = np.ones(len(g), bool)
    garde[aff] = False
    c = gpd.GeoDataFrame(pd.concat([g[garde], r, p], ignore_index=True), geometry="geometry", crs=2154)
    i, j = adjacence(c.geometry.values)
    np.savez_compressed(out / "topo_2021c.npz", i=i, j=j)
    c.to_parquet(out / "ocsge_2021c.parquet")
    log(dep, "patch", len(p), "polygones corrigés")


def classer(dep, out):
    R = regles()
    for a in ["2021", "2024"] + (["2021c"] if (out / "ocsge_2021c.parquet").exists() else []):
        if (out / f"artif_{a}.parquet").exists():
            continue
        g = gpd.read_parquet(out / f"ocsge_{a}.parquet")
        z = np.load(out / f"topo_{a}.npz")
        topo = (z["i"], z["j"], np.zeros(len(g), bool))
        cols = {}
        for nom, r in (R.items() if a != "2021c" else [("reference", R["reference"])]):
            fin, _ = seuiller(g, classer_brut(g, r), r, topo)
            cols[nom] = fin.to_numpy()
        pd.DataFrame(cols).to_parquet(out / f"artif_{a}.parquet")
        log(dep, a, "classé")
        del g
        gc.collect()


# ------------------------------------------------------------------ 3-4. cartes, statistiques, destinations
def grille_web(g3):
    minx, miny, maxx, maxy = g3.total_bounds
    res = 10.0
    while ((maxx - minx) / res) * ((maxy - miny) / res) > MAXPX:
        res *= 1.25
    res = round(res, 1)
    minx, miny = math.floor(minx / res) * res, math.floor(miny / res) * res
    return res, minx, miny, int(math.ceil((maxx - minx) / res)), int(math.ceil((maxy - miny) / res))


def batches(f):
    for b in pq.ParquetFile(f).iter_batches(batch_size=B):
        yield b, shapely.from_wkb(b.column("geometry").to_numpy(zero_copy_only=False))


def produire(dep, out, meta):
    y1, y2 = meta["y1"], meta["y2"]
    NY = int(y2) - int(y1)
    web = ROOT / "web" / dep
    web.mkdir(parents=True, exist_ok=True)
    com = communes(dep)
    nom = pd.read_csv(CONFIG / "nomenclature_ocsge.csv", sep=";")
    cs = nom[nom.CODE.str.startswith("CS")].reset_index(drop=True)
    csi = {c: i + 1 for i, c in enumerate(cs.CODE)}
    comw = com.to_crs(3857)
    res, minx, miny, W, Hh = grille_web(comw)
    tr = from_origin(minx, miny + Hh * res, res, res)
    maskw = rasterio.features.rasterize(zip(comw.geometry, [1] * len(comw)), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint8") == 0
    x0, y0, x1, y1_ = com.total_bounds
    rs = 5.0 if (x1 - x0) * (y1_ - y0) / 25 < 1.5e8 else (10.0 if (x1 - x0) * (y1_ - y0) / 100 < 6e7 else 15.0)
    W5, H5 = int(math.ceil((x1 - x0) / rs)), int(math.ceil((y1_ - y0) / rs))
    tr5 = from_origin(x0, y1_, rs, rs)
    cid = rasterio.features.rasterize(zip(com.geometry, range(1, len(com) + 1)), out_shape=(H5, W5), transform=tr5, fill=0, dtype="uint16")
    nC, px, G = len(com) + 1, rs * rs / 1e4, len(DEST)
    tw = Transformer.from_crs(2154, 3857, always_xy=True)
    to3857 = lambda geo: shapely.transform(geo, lambda xy: np.column_stack(tw.transform(xy[:, 0], xy[:, 1])))  # noqa: E731
    corr = (out / "artif_2021c.parquet").exists()
    VAR = BASE + (["corrige"] if corr else [])
    webA, statA, dstA, leg = {}, {}, {}, {}
    couches = [("2021", "2021", BASE), ("2024", "2024", BASE)] + ([("2021c", "2021", ["corrige"])] if corr else [])
    for f, slot, vs in couches:
        art = pd.read_parquet(out / f"artif_{f}.parquet")
        cov = np.zeros((Hh, W), np.uint8) if f == "2021" else None
        dd = np.zeros((H5, W5), np.uint8) if f in ("2021", "2024") else None
        for v in vs:
            webA[(slot, v)] = np.zeros((Hh, W), np.uint8)
            statA[(slot, v)] = np.zeros((H5, W5), np.uint8)
        o = 0
        for b, geo in batches(out / f"ocsge_{f}.parquet"):
            gw = to3857(geo)
            if cov is not None:
                rasterio.features.rasterize(zip(gw, pd.Series(b.column("code_cs").to_pylist()).map(csi).fillna(0).astype(int)), out=cov, transform=tr, dtype="uint8")
            if dd is not None:
                rasterio.features.rasterize(zip(geo, dest_us(pd.Series(b.column("code_us").to_pylist())) + 1), out=dd, transform=tr5, dtype="uint8")
            for v in vs:
                vals = np.where(art["reference" if v == "corrige" else v].to_numpy()[o:o + len(geo)], 2, 1)
                rasterio.features.rasterize(zip(gw, vals), out=webA[(slot, v)], transform=tr, dtype="uint8")
                rasterio.features.rasterize(zip(geo, vals), out=statA[(slot, v)], transform=tr5, dtype="uint8")
            o += len(geo)
            del gw, geo, b
            gc.collect()
        assert o == len(art)
        if cov is not None:
            cov[maskw] = 0
            pal = [(0, 0, 0)] + [tuple(x) for x in cs[["R", "V", "B"]].to_numpy()]
            save_png(cov, pal, web / "couverture_2021.png")
            leg["couverture_2021"] = [{"code": cs.CODE[i - 1], "label": cs.LIBELLE[i - 1].strip(), "color": "#%02x%02x%02x" % pal[i]}
                                      for i in sorted(set(np.unique(cov)) - {0})]
        if dd is not None:
            dstA[slot] = dd
        log(dep, f, "rasters")
    if corr:
        webA[("2024", "corrige")] = webA[("2024", "reference")].copy()
        statA[("2024", "corrige")] = statA[("2024", "reference")].copy()
    for v in VAR:
        a21, a24 = webA.pop(("2021", v)), webA.pop(("2024", v))
        a21[maskw] = 0
        a24[maskw] = 0
        sfx, esf = ("_ref", "") if v == "reference" else (f"_{v}", f"_{v}")
        save_png(a21, [H(c) for c in ART], web / f"artif_2021{sfx}.png")
        ev = np.zeros_like(a24)
        ev[(a21 == 1) & (a24 == 1)] = 1
        ev[(a21 == 2) & (a24 == 2)] = 2
        ev[(a21 == 1) & (a24 == 2)] = 3
        ev[(a21 == 2) & (a24 == 1)] = 4
        save_png(ev, [H(c) for c in EV], web / f"evolution_2021_2024{esf}.png")
        leg[f"artif_2021{sfx}"] = [{"code": "0", "label": "Non artificialisé", "color": "#e3eae5"},
                                   {"code": "1", "label": "Artificialisé", "color": "#c8452f"}]
        leg[f"evolution_2021_2024{esf}"] = [
            {"code": "1", "label": "Non artificialisé (stable)", "color": "#eef2ef"},
            {"code": "2", "label": "Artificialisé (stable)", "color": "#d6d3dc"},
            {"code": "3", "label": "Nouvellement artificialisé", "color": "#c8452f"},
            {"code": "4", "label": "Désartificialisé", "color": "#297254"}]
    cidw = rasterio.features.rasterize(zip(comw.geometry, range(1, len(comw) + 1)), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint16")
    rgb = np.zeros((Hh, W, 4), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 3] = cidw >> 8, cidw & 255, np.where(cidw > 0, 255, 0)
    Image.fromarray(rgb, "RGBA").save(web / "communes_idx.png", optimize=True)
    del cidw, rgb, maskw
    gc.collect()

    per = f"{y1}-{y2}"
    ind = {c: {"surface_ha": round(float(a), 1), "stock": {}, "flux": {}, "flux_brut": {}} for c, a in zip(com.insee, com.geometry.area / 1e4)}
    dept = {"surface_ha": round(float(com.geometry.area.sum() / 1e4), 0), "stock": {}, "flux": {}, "flux_brut": {}}
    for v in VAR:
        a, b = statA[("2021", v)], statA[("2024", v)]
        s1 = np.bincount(cid[a == 2], minlength=nC) * px
        s2 = np.bincount(cid[b == 2], minlength=nC) * px
        gain = np.bincount(cid[(a == 1) & (b == 2)], minlength=nC) * px / NY
        perte = np.bincount(cid[(a == 2) & (b == 1)], minlength=nC) * px / NY
        for k, c in enumerate(com.insee, start=1):
            ind[c]["stock"][v] = {"2021": round(float(s1[k]), 1), "2024": round(float(s2[k]), 1)}
            ind[c]["flux"][v] = {"2021-2024": round(float(s2[k] - s1[k]) / NY, 2)}
            ind[c]["flux_brut"][v] = {"artif": round(float(gain[k]), 2), "desartif": round(float(perte[k]), 2)}
        dept["stock"][v] = {"2021": round(float(s1[1:].sum()), 0), "2024": round(float(s2[1:].sum()), 0)}
        dept["flux"][v] = {"2021-2024": round(float(s2[1:].sum() - s1[1:].sum()) / NY, 1)}
        dept["flux_brut"][v] = {"artif": round(float(gain[1:].sum()), 2), "desartif": round(float(perte[1:].sum()), 2)}
    # destinations OCS GE (règle officielle)
    a, b = statA[("2021", "reference")], statA[("2024", "reference")]
    mg, mp = (cid > 0) & (a == 1) & (b == 2), (cid > 0) & (a == 2) & (b == 1)
    og = np.bincount(cid[mg].astype(np.int64) * G + dstA["2024"][mg] - 1, minlength=nC * G).reshape(nC, G) * px / NY
    op = np.bincount(cid[mp].astype(np.int64) * G + dstA["2021"][mp] - 1, minlength=nC * G).reshape(nC, G) * px / NY
    del statA, dstA
    gc.collect()

    # Fichiers fonciers, alignés exactement sur y1-y2
    an = [f"{y % 100:02d}" for y in range(int(y1), int(y2) + 1)]
    pairs = list(zip(an[:-1], an[1:]))
    typ = {"hab": ["hab"], "act": ["act"], "mix": ["mix"], "infra": ["rou", "fer"], "autre": ["inc"]}
    cols = [f"naf{p}art{q}" for p, q in pairs] + [f"art{p}{t}{q}" for p, q in pairs for ts in typ.values() for t in ts]
    cer = pd.read_csv(RAW / "cerema" / "conso_com_2011_2025.csv", dtype={"idcom": str}, low_memory=False, usecols=["idcom"] + cols).set_index("idcom")
    cer = cer[cer.index.isin(com.insee)]
    tot = cer[[f"naf{p}art{q}" for p, q in pairs]].sum(axis=1) / 1e4 / NY
    FF = np.zeros((nC, G))
    pos = {c: k for k, c in enumerate(com.insee, start=1)}
    for dname, ts in typ.items():
        v = cer[[f"art{p}{t}{q}" for p, q in pairs for t in ts]].sum(axis=1) / 1e4 / NY
        for c, x in v.items():
            FF[pos[c], DEST.index(dname)] = x
    for c in cer.index:
        ind[c]["cerema"] = {per: round(float(tot[c]), 2)}
    dept["cerema"] = {per: round(float(tot.sum()), 2)}

    c4 = com.to_crs(4326)
    c4["geometry"] = c4.geometry.simplify(0.0001, preserve_topology=True)
    gj = json.loads(c4[["insee", "nom", "geometry"]].to_json())

    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]
    for ftr in gj["features"]:
        ftr["geometry"]["coordinates"] = rnd(ftr["geometry"]["coordinates"])
        ftr.pop("id", None)
    t = Transformer.from_crs(3857, 4326, always_xy=True)
    lon0, lat0 = t.transform(minx, miny)
    lon1, lat1 = t.transform(minx + W * res, miny + Hh * res)
    src = {"mos_nom": None, "ocsge_annees": [y1, y2], "ff_periode": per, "ocsge_millesimes": meta["millesimes"],
           "corrige": corr, "carte_legere": True}
    data = {"dep": dep, "sources": src, "res_m": res, "bounds": [[lat0, lon0], [lat1, lon1]], "legendes": leg,
            "communes": gj, "indicateurs": ind, "departement": dept}
    (web / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    r2 = lambda x: round(float(x), 2)  # noqa: E731

    def bloc(k):
        f = (lambda x: x[1:].sum(axis=0)) if k is None else (lambda x: x[k])
        return {"usages": {"ocs_gain": {DEST[i]: r2(f(og)[i]) for i in range(G)}, "ocs_perte": {DEST[i]: r2(f(op)[i]) for i in range(G)},
                           "ff": {DEST[i]: r2(f(FF)[i]) for i in range(G)}}}
    det = {"dep": dep, "pas_m": rs, "periodes": {"ocs": [y1, y2], "ff": [y1, y2]}, "destinations": DEST_LIB,
           "departement": bloc(None), "communes": {c: bloc(k) for k, c in enumerate(com.insee, start=1)}}
    (web / "details.json").write_text(json.dumps(det, ensure_ascii=False, separators=(",", ":")))
    resume = {"dep": dep, "y1": y1, "y2": y2, "corrige": corr, "communes": len(com), "surface_ha": dept["surface_ha"],
              "stock_y1": dept["stock"]["reference"]["2021"], "stock_y2": dept["stock"]["reference"]["2024"],
              "ocs_brut": dept["flux_brut"]["reference"]["artif"], "ocs_retour": dept["flux_brut"]["reference"]["desartif"],
              "ocs_net": dept["flux"]["reference"]["2021-2024"], "ocs_net_corrige": dept["flux"].get("corrige", {}).get("2021-2024"),
              "ff": dept["cerema"][per], "dest_ocs": det["departement"]["usages"]["ocs_gain"], "dest_ff": det["departement"]["usages"]["ff"],
              "res_web_m": res, "web_mo": round(sum(p.stat().st_size for p in web.iterdir()) / 1e6, 1)}
    (web / "resume.json").write_text(json.dumps(resume, ensure_ascii=False))
    log(dep, "fini", json.dumps({k: resume[k] for k in ["y1", "y2", "ocs_brut", "ocs_net", "ocs_net_corrige", "ff", "web_mo"]}))
    return resume


def main(dep, garder=False):
    out = PROCESSED / dep
    out.mkdir(parents=True, exist_ok=True)
    raw = RAW / "ocsge" / "france"
    raw.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    meta = preparer(dep, out, raw)
    classer(dep, out)
    r = produire(dep, out, meta)
    r["minutes"] = round((time.time() - t0) / 60, 1)
    (ROOT / "web" / dep / "resume.json").write_text(json.dumps(r, ensure_ascii=False))
    if not garder:
        shutil.rmtree(out, ignore_errors=True)
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dep")
    ap.add_argument("--garder", action="store_true")
    a = ap.parse_args()
    main(a.dep.upper(), a.garder)
