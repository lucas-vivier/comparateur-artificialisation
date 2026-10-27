"""Chaîne complète pour un département : OCS GE (2021, 2024) + MOS IDF + Fichiers fonciers -> web/<dep>/.

Usage : python scripts/pipeline_dep.py 77 [--etapes prep,classe,web,stats]
Chaque étape met son résultat en cache dans data/processed/<dep>/ et peut être relancée seule.

Différences avec les scripts export_web*.py (département 94) :
- limite de l'emprise prise sur les contours communaux (tampon 30 m) au lieu de l'union des polygones ;
- résolution des images adaptée à la taille du département (≈ 16 Mpx au plus) ;
- statistiques par commune sur une grille Lambert-93 (5 m, ou 10 m pour les grands départements) ;
- index des communes encodé sur 16 bits (rouge = poids fort, vert = poids faible).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import py7zr
import pyogrio
import pyarrow.parquet
import rasterio.features
from PIL import Image
from pyproj import Transformer
from rasterio.transform import from_origin

from occsol import mos
from occsol.nomenclature import Regle, adjacence, classer_brut, seuiller
from occsol.paths import CONFIG, PROCESSED, RAW, ROOT

VARIANTES = ["reference", "sans_herbace", "seuil_0", "seuil_1000", "seuil_5000", "corrige"]
BASE = [v for v in VARIANTES if v != "corrige"]  # variantes de règle ; "corrige" = règle officielle sur le 2021 corrigé (patch IGN)
ANNEES = ["2021", "2024"]  # emplacements internes : "2024" = second millésime (2025 pour le Nord)
HDF = {"02", "59", "60", "62", "80"}
BZH = {"22", "29"}  # MOS foncier breton (Région Bretagne) 2011/2021/2024
BZH_GRP = ["NATUREL ET FORESTIER", "AGRICOLE", "CARRIERES", "SURFACES EN EAU", "HABITAT", "URBAIN MIXTE ET BATI DIVERS",
           "ACTIVITES ET COMMERCES", "EQUIPEMENTS", "INFRASTRUCTURES", "DEFENSE"]
BZH_COUL = ["#8FC79A", "#EDE3A0", "#C9BA5B", "#7FC8EE", "#FBC49B", "#EF7A50", "#D99BC0", "#A57DB8", "#B5B5B5", "#8C9474"]
BZH_LIB = ["Naturel et forestier", "Agricole", "Carrières", "Surfaces en eau", "Habitat", "Urbain mixte et bâti divers",
           "Activités et commerces", "Équipements", "Infrastructures", "Défense"]
Y2 = {"59": "2025", "22": "2025"}  # second millésime OCS GE quand il n'est pas 2024
ENAF_HDF = RAW / "hdf" / "ocs2d_enaf_2024_v2.gpkg"
HDF_CODES = {"Agricole": 1, "Forêt": 2, "Naturel": 3, "Habitat": 4, "Activité": 5, "Urbanisé autre": 6, "Infrastructure": 7}
HDF_COUL = {1: "#EDE3A0", 2: "#8FC79A", 3: "#C9BA5B", 4: "#FBC49B", 5: "#D99BC0", 6: "#A57DB8", 7: "#B5B5B5"}


def y2(dep):
    return Y2.get(dep, "2024")
H = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
ART = ["#000000", "#E3EAE5", "#C8452F"]
EV = ["#000000", "#EEF2EF", "#D6D3DC", "#C8452F", "#297254"]
COUL12 = {1: "#8FC79A", 2: "#C9BA5B", 3: "#EDE3A0", 4: "#7FC8EE", 5: "#CFE5C9", 6: "#FBC49B",
          7: "#EF7A50", 8: "#D99BC0", 9: "#45BBB2", 10: "#A57DB8", 11: "#B5B5B5", 12: "#8C9474"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def regles():
    import yaml
    ref = Regle.reference()
    conf = yaml.safe_load((CONFIG / "scenarios.yaml").read_text())
    out = {}
    for nom in BASE:
        kw = {k: tuple(v) if isinstance(v, list) else v for k, v in (conf.get(nom) or {}).items()}
        out[nom] = ref.variante(nom, **kw)
    return out


def communes(dep):
    com = gpd.read_file(RAW / "communes" / f"communes_{dep}.geojson").to_crs(2154).rename(columns={"code": "insee"})
    return com[["insee", "nom", "geometry"]].reset_index(drop=True)


def norm_insee(s: pd.Series) -> pd.Series:
    """Arrondissements de Paris (751xx) -> commune 75056."""
    return s.where(~s.str.match(r"^751\d\d$"), "75056")


# ---------------------------------------------------------------- étape prep
def prep(dep, out):
    com = communes(dep)
    for a in ANNEES:
        f = out / f"ocsge_{a}.parquet"
        if f.exists():
            continue
        ya = y2(dep) if a == "2024" else a
        arch = RAW / "ocsge" / "ocsge" / f"OCS-GE_2-0__GPKG_LAMB93_D0{dep}_{ya}-01-01.7z"
        tmp = out / f"x_{a}"
        with py7zr.SevenZipFile(arch) as z:
            names = [n for n in z.getnames() if n.endswith("OCCUPATION_SOL.gpkg")]
            z.extract(tmp, targets=names)
        g = gpd.read_file(next(tmp.rglob("OCCUPATION_SOL.gpkg")), columns=["code_cs", "code_us"], engine="pyogrio")
        g = g.explode(index_parts=False).reset_index(drop=True)
        log(dep, a, len(g), "polygones")
        i, j = adjacence(g.geometry.values)
        au_bord = np.zeros(len(g), bool)  # plus utilisé : le seuillage n'exclut plus le bord (voir classe)
        np.savez_compressed(out / f"topo_{a}.npz", i=i, j=j, bord=au_bord)
        g.to_parquet(f)
        log(dep, a, "topologie ok", int(au_bord.sum()), "au bord")


# ---------------------------------------------------------------- étape classe
def classe(dep, out):
    """Statut artificialisé par polygone, seuillage itératif. 2021c = millésime 2021 corrigé (règle officielle)."""
    R = regles()
    couches = list(ANNEES) + (["2021c"] if (out / "ocsge_2021c.parquet").exists() else [])
    for a in couches:
        if (out / f"artif_{a}.parquet").exists():
            continue
        cols = {}
        g = gpd.read_parquet(out / f"ocsge_{a}.parquet")
        z = np.load(out / f"topo_{a}.npz")
        # Pas d'exclusion des groupes au bord de l'emprise : c'est ce qui reproduit la couche IGN
        # (Val-de-Marne 2021 : 0,4 ha d'écart sans exclusion contre 17 ha avec un tampon de 30 m).
        topo = (z["i"], z["j"], np.zeros(len(g), bool))
        for nom, r in (R.items() if a != "2021c" else [("reference", R["reference"])]):
            brut = classer_brut(g, r)
            fin, _ = seuiller(g, brut, r, topo)
            cols[nom] = fin.to_numpy()
        pd.DataFrame(cols).to_parquet(out / f"artif_{a}.parquet")
        log(dep, a, "classé")
        del g
        import gc
        gc.collect()


# ---------------------------------------------------------------- grilles
def grille_web(g3):
    minx, miny, maxx, maxy = g3.total_bounds
    res = 8.0
    while ((maxx - minx) / res) * ((maxy - miny) / res) > 16e6:
        res *= 1.25
    res = round(res, 1)
    minx, miny = math.floor(minx / res) * res, math.floor(miny / res) * res
    W, Hh = int(math.ceil((maxx - minx) / res)), int(math.ceil((maxy - miny) / res))
    return res, minx, miny, W, Hh


def save_png(arr, palette, path):
    img = Image.fromarray(arr.astype(np.uint8), mode="P")
    flat = [c for rgb in palette for c in rgb]
    img.putpalette(flat + [0] * (768 - len(flat)))
    img.save(path, optimize=True, transparency=0)


# ---------------------------------------------------------------- étape web + stats
def web_stats(dep, out):
    """Version économe en mémoire : une couche à la fois (le 77 dépasse 8 Go sinon)."""
    import gc
    web = ROOT / "web" / dep
    web.mkdir(parents=True, exist_ok=True)
    com = communes(dep)
    nom = pd.read_csv(CONFIG / "nomenclature_ocsge.csv", sep=";")
    cs = nom[nom.CODE.str.startswith("CS")].reset_index(drop=True)
    comw = com.to_crs(3857)
    res, minx, miny, W, Hh = grille_web(comw)
    tr = from_origin(minx, miny + Hh * res, res, res)
    rast = lambda geo, v: rasterio.features.rasterize(zip(geo, v), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint8")  # noqa: E731
    x0, y0, x1, y1 = com.total_bounds
    rs = 5.0 if (x1 - x0) * (y1 - y0) / 25 < 1.5e8 else (10.0 if (x1 - x0) * (y1 - y0) / 100 < 6e7 else 15.0)
    W5, H5 = int(math.ceil((x1 - x0) / rs)), int(math.ceil((y1 - y0) / rs))
    tr5 = from_origin(x0, y1, rs, rs)
    r5 = lambda geo, v, dt="uint8": rasterio.features.rasterize(zip(geo, v), out_shape=(H5, W5), transform=tr5, fill=0, dtype=dt)  # noqa: E731
    cid = r5(com.geometry, range(1, len(com) + 1), "uint16")
    nC = len(com) + 1
    px = rs * rs / 1e4
    leg, webA, statA = {}, {}, {}
    NY = int(y2(dep)) - 2021
    for a in ANNEES:
        # par morceaux de 100 000 polygones pour tenir en mémoire (Pas-de-Calais, Nord)
        art = pd.read_parquet(out / f"artif_{a}.parquet")
        pf = pyarrow.parquet.ParquetFile(out / f"ocsge_{a}.parquet")
        csi = {c: i + 1 for i, c in enumerate(cs.CODE)}
        arr = np.zeros((Hh, W), np.uint8)
        for v in BASE:
            webA[(a, v)] = np.zeros((Hh, W), np.uint8)
            statA[(a, v)] = np.zeros((H5, W5), np.uint8)
        off = 0
        for batch in pf.iter_batches(batch_size=100000):
            gb = gpd.GeoDataFrame.from_arrow(batch) if hasattr(gpd.GeoDataFrame, "from_arrow") else gpd.read_parquet(out / f"ocsge_{a}.parquet").iloc[off:off + len(batch)]
            gb = gb.set_crs(2154, allow_override=True)
            gw = gb.geometry.to_crs(3857)
            sl = slice(off, off + len(gb))
            if a == "2021":
                rasterio.features.rasterize(zip(gw, gb.code_cs.map(csi).fillna(0).astype(int)), out=arr, transform=tr, dtype="uint8")
            for v in BASE:
                vals = np.where(art[v].to_numpy()[sl], 2, 1)
                rasterio.features.rasterize(zip(gw, vals), out=webA[(a, v)], transform=tr, dtype="uint8")
                rasterio.features.rasterize(zip(gb.geometry, vals), out=statA[(a, v)], transform=tr5, dtype="uint8")
            off += len(gb)
            del gb, gw
            gc.collect()
        assert off == len(art), (off, len(art))
        if a == "2021":
            pal = [(0, 0, 0)] + [tuple(x) for x in cs[["R", "V", "B"]].to_numpy()]
            save_png(arr, pal, web / "couverture_2021.png")
            leg["couverture_2021"] = [{"code": cs.CODE[i - 1], "label": cs.LIBELLE[i - 1].strip(), "color": "#%02x%02x%02x" % pal[i]}
                                      for i in sorted(set(np.unique(arr)) - {0})]
        del arr, art
        gc.collect()
        log(dep, a, "rasters")
    # millésime 2021 corrigé (patch IGN) : seule la couche 2021 change ; 2024 = référence
    corr = (out / "artif_2021c.parquet").exists()
    if corr:
        art = pd.read_parquet(out / "artif_2021c.parquet")["reference"].to_numpy()
        webA[("2021", "corrige")] = np.zeros((Hh, W), np.uint8)
        statA[("2021", "corrige")] = np.zeros((H5, W5), np.uint8)
        off = 0
        for batch in pyarrow.parquet.ParquetFile(out / "ocsge_2021c.parquet").iter_batches(batch_size=100000):
            gb = gpd.GeoDataFrame.from_arrow(batch).set_crs(2154, allow_override=True)
            vals = np.where(art[off:off + len(gb)], 2, 1)
            rasterio.features.rasterize(zip(gb.geometry.to_crs(3857), vals), out=webA[("2021", "corrige")], transform=tr, dtype="uint8")
            rasterio.features.rasterize(zip(gb.geometry, vals), out=statA[("2021", "corrige")], transform=tr5, dtype="uint8")
            off += len(gb)
            del gb
            gc.collect()
        assert off == len(art)
        webA[("2024", "corrige")] = webA[("2024", "reference")].copy()
        statA[("2024", "corrige")] = statA[("2024", "reference")].copy()
        del art
        log(dep, "2021 corrigé", "rasters")
    VAR = VARIANTES if corr else BASE
    for v in VAR:
        a21, a24 = webA.pop(("2021", v)), webA.pop(("2024", v))
        sfx = "_ref" if v == "reference" else f"_{v}"
        esf = "" if v == "reference" else f"_{v}"
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
    log(dep, "images OCS GE", W, Hh, res)

    ind = {c: {"surface_ha": round(float(ar), 1), "stock": {}, "flux": {}, "flux_brut": {}}
           for c, ar in zip(com.insee, com.geometry.area / 1e4)}
    dept = {"surface_ha": round(float(com.geometry.area.sum() / 1e4), 0), "stock": {}, "flux": {}, "flux_brut": {}}
    for v in VAR:
        a, b = statA[("2021", v)], statA[("2024", v)]
        s21 = np.bincount(cid[a == 2], minlength=nC) * px
        s24 = np.bincount(cid[b == 2], minlength=nC) * px
        gain = np.bincount(cid[(a == 1) & (b == 2)], minlength=nC) * px / NY
        perte = np.bincount(cid[(a == 2) & (b == 1)], minlength=nC) * px / NY
        for k, c in enumerate(com.insee, start=1):
            ind[c]["stock"][v] = {"2021": round(float(s21[k]), 1), "2024": round(float(s24[k]), 1)}
            ind[c]["flux"][v] = {"2021-2024": round(float(s24[k] - s21[k]) / NY, 2)}
            ind[c]["flux_brut"][v] = {"artif": round(float(gain[k]), 2), "desartif": round(float(perte[k]), 2)}
        dept["stock"][v] = {"2021": round(float(s21[1:].sum()), 0), "2024": round(float(s24[1:].sum()), 0)}
        dept["flux"][v] = {"2021-2024": round(float(s24[1:].sum() - s21[1:].sum()) / NY, 1)}
        dept["flux_brut"][v] = {"artif": round(float(gain[1:].sum()), 2), "desartif": round(float(perte[1:].sum()), 2)}
    a21r = statA[("2021", "reference")]
    for k in list(statA):
        if k != ("2021", "reference"):
            del statA[k]
    gc.collect()
    log(dep, "stats OCS GE", "grille", rs)

    # MOS (IDF : Institut Paris Region ; HdF : OCS2D, couche ENAF de la Région) — lu et rastérisé par morceaux
    if dep in HDF:
        det_leg = [{"code": str(c), "label": kk, "color": HDF_COUL[c], "urb": c >= 4} for kk, c in HDF_CODES.items()]
        det_pal = [(0, 0, 0)] + [H(HDF_COUL[i]) for i in range(1, 8)]
        NYM = int(y2(dep)) - 2021
        src = {"mos_nom": "OCS2D", "mos_producteur": "Région Hauts-de-France, Géo2France", "mos_annees": ["2021", y2(dep)],
               "mos_licence": "Licence ouverte 2.0", "mos_enaf": "classement NAF / non-NAF de la Région"}
        bb = tuple(com.total_bounds)
        ntot = pyogrio.read_info(ENAF_HDF, layer="ocs2d_enaf_opendata")["features"]

        def morceaux():
            for off in range(0, ntot, 300000):
                c = gpd.read_file(ENAF_HDF, layer="ocs2d_enaf_opendata", bbox=bb, engine="pyogrio", skip_features=off,
                                  max_features=300000, columns=["enaf_2021", "urba_2021", "urba_2024"])
                if c.empty:
                    continue
                c = c[c.urba_2021.isin(["NAF", "Non-NAF"]) & c.urba_2024.isin(["NAF", "Non-NAF"])]
                yield pd.DataFrame({"naf2021": (c.urba_2021 == "NAF").astype(int).to_numpy(),
                                    "naf2025": (c.urba_2024 == "NAF").astype(int).to_numpy(),
                                    "g2021": c.enaf_2021.map(HDF_CODES).fillna(0).astype(int).to_numpy()}), c.geometry
    elif dep in BZH:
        nb = pd.read_csv(CONFIG / "mos_bretagne_nomenclature.csv", sep=";", dtype={"code": str}).set_index("code")
        grp = nb.regroupement.map({g: i + 1 for i, g in enumerate(BZH_GRP)})
        det_leg = [{"code": str(i + 1), "label": BZH_LIB[i], "color": BZH_COUL[i], "urb": i >= 4} for i in range(len(BZH_GRP))]
        det_pal = [(0, 0, 0)] + [H(c) for c in BZH_COUL]
        NYM = 3
        src = {"mos_nom": "MOS breton", "mos_producteur": "Région Bretagne", "mos_annees": ["2021", "2024"],
               "mos_licence": "Licence ouverte 2.0", "mos_enaf": "classement ENAF du producteur",
               "mos_detail": "10 regroupements du MOS foncier"}

        def morceaux():
            for part in sorted((RAW / "bzh" / f"mos_bzh_{dep}").glob("part_*.parquet")):
                m = gpd.read_parquet(part).to_crs(2154)
                c21, c24 = m.code4_2021.astype(str).str[:4], m.code4_2024.astype(str).str[:4]
                ok = c21.isin(nb.index) & c24.isin(nb.index)
                m, c21, c24 = m[ok], c21[ok], c24[ok]
                yield pd.DataFrame({"naf2021": c21.map(nb.enaf).astype(int).to_numpy(),
                                    "naf2025": c24.map(nb.enaf).astype(int).to_numpy(),
                                    "g2021": c21.map(grp).astype(int).to_numpy()}), m.geometry
    else:
        nm = mos.nomenclature().set_index("code")
        lab12 = nm.drop_duplicates("groupe12").set_index("groupe12").libelle12
        det_leg = [{"code": str(i), "label": lab12[i], "color": COUL12[i], "urb": i >= 5} for i in range(1, 13)]
        det_pal = [(0, 0, 0)] + [H(COUL12[i]) for i in range(1, 13)]
        NYM = 4
        src = {"mos_nom": "MOS", "mos_producteur": "Institut Paris Region", "mos_annees": ["2021", "2025"],
               "mos_licence": "Licence ouverte", "mos_enaf": "postes 1 à 12 = ENAF"}

        def morceaux():
            m = mos.telecharger(dep)
            yield pd.DataFrame({"naf2021": m.mos2021.map(nm.enaf).astype(int).to_numpy(),
                                "naf2025": m.mos2025.map(nm.enaf).astype(int).to_numpy(),
                                "g2021": m.mos2021.map(nm.groupe12).astype(int).to_numpy()}), m.geometry
    Wdet, Wbin, Wevo = (np.zeros((Hh, W), np.uint8) for _ in range(3))
    m21, m25 = np.zeros((H5, W5), np.uint8), np.zeros((H5, W5), np.uint8)
    nm_tot = 0
    for att, geo in morceaux():
        nm_tot += len(att)
        gw = geo.to_crs(3857)
        ev = np.select([(att.naf2021 == 1) & (att.naf2025 == 1), (att.naf2021 == 0) & (att.naf2025 == 0),
                        (att.naf2021 == 1) & (att.naf2025 == 0)], [1, 2, 3], 4)
        for arr_, vals, g_, tr_ in [(Wdet, att.g2021, gw, tr), (Wbin, np.where(att.naf2021 == 1, 1, 2), gw, tr), (Wevo, ev, gw, tr),
                                    (m21, np.where(att.naf2021 == 0, 2, 1), geo, tr5), (m25, np.where(att.naf2025 == 0, 2, 1), geo, tr5)]:
            rasterio.features.rasterize(zip(g_, vals), out=arr_, transform=tr_, dtype="uint8")
        del gw, geo, att, ev
        gc.collect()
    log(dep, "MOS", nm_tot)
    maskw = rasterio.features.rasterize(zip(comw.geometry, [1] * len(comw)), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint8") == 0
    for arr_ in (Wdet, Wbin, Wevo):
        arr_[maskw] = 0
    m21[cid == 0] = 0
    m25[cid == 0] = 0
    save_png(Wdet, det_pal, web / "mos_2021.png")
    present = set(np.unique(Wdet)) - {0}
    leg["mos_2021"] = [e for e in det_leg if int(e["code"]) in present]
    save_png(Wbin, [(0, 0, 0), H("#E3EAE5"), H("#000091")], web / "mos_enaf_2021.png")
    leg["mos_enaf_2021"] = [{"code": "1", "label": "ENAF (naturel, agricole, forestier)", "color": "#E3EAE5"},
                            {"code": "2", "label": "Urbanisé", "color": "#000091"}]
    save_png(Wevo, [H(c) for c in EV], web / "mos_evolution_2021_2025.png")
    leg["mos_evolution_2021_2025"] = [
        {"code": "1", "label": "ENAF (stable)", "color": "#EEF2EF"}, {"code": "2", "label": "Urbanisé (stable)", "color": "#D6D3DC"},
        {"code": "3", "label": "ENAF consommé", "color": "#C8452F"}, {"code": "4", "label": "Retour en ENAF", "color": "#297254"}]
    del Wdet, Wbin, Wevo, maskw
    cidw = rasterio.features.rasterize(zip(comw.geometry, range(1, len(comw) + 1)), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint16")
    rgb = np.zeros((Hh, W, 4), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 3] = cidw >> 8, cidw & 255, np.where(cidw > 0, 255, 0)
    Image.fromarray(rgb, "RGBA").save(web / "communes_idx.png", optimize=True)
    del cidw, rgb
    gc.collect()
    log(dep, "images MOS + communes")
    u21 = np.bincount(cid[m21 == 2], minlength=nC) * px
    u25 = np.bincount(cid[m25 == 2], minlength=nC) * px
    conso = np.bincount(cid[(m21 == 1) & (m25 == 2)], minlength=nC) * px
    retour = np.bincount(cid[(m21 == 2) & (m25 == 1)], minlength=nC) * px
    both = (a21r > 0) & (m21 > 0) & (cid > 0)
    agree = np.bincount(cid[both & (a21r == m21)], minlength=nC)
    tot = np.bincount(cid[both], minlength=nC)
    ocs_seul = np.bincount(cid[both & (a21r == 2) & (m21 == 1)], minlength=nC) * px
    mos_seul = np.bincount(cid[both & (a21r == 1) & (m21 == 2)], minlength=nC) * px

    def bloc(k):
        sl = slice(1, None) if k is None else k
        f = lambda x: float(x[sl].sum()) if k is None else float(x[k])  # noqa: E731
        t = f(tot)
        return {"urbain_2021": round(f(u21), 1), "urbain_2025": round(f(u25), 1),
                "conso_brute_ha_an": round(f(conso) / NYM, 2), "conso_nette_ha_an": round((f(conso) - f(retour)) / NYM, 2),
                "accord_2021": round(f(agree) / t, 4) if t else None,
                "ocs_seul_ha": round(f(ocs_seul), 1), "mos_seul_ha": round(f(mos_seul), 1)}
    for k, c in enumerate(com.insee, start=1):
        if tot[k]:
            ind[c]["mos"] = bloc(k)
    dept["mos"] = bloc(None)
    # Fichiers fonciers (Cerema)
    cer = pd.read_csv(RAW / "cerema" / "conso_com_2011_2025.csv", dtype={"idcom": str}, low_memory=False,
                      usecols=["idcom", "naf21art22", "naf22art23", "naf23art24", "naf24art25"]).set_index("idcom")
    cer = cer[cer.index.isin(com.insee)]
    f24 = (cer.naf21art22 + cer.naf22art23 + cer.naf23art24) / 1e4 / 3
    f25 = (cer.naf21art22 + cer.naf22art23 + cer.naf23art24 + cer.naf24art25) / 1e4 / 4
    for c in cer.index:
        ind[c]["cerema"] = {"2021-2024": round(float(f24[c]), 2), "2021-2025": round(float(f25[c]), 2)}
    dept["cerema"] = {"2021-2024": round(float(f24.sum()), 2), "2021-2025": round(float(f25.sum()), 2)}

    # communes (GeoJSON simplifié WGS84) et bornes
    c4 = com.to_crs(4326)
    c4["geometry"] = c4.geometry.simplify(0.00006, preserve_topology=True)
    gj = json.loads(c4[["insee", "nom", "geometry"]].to_json())
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]
    for ftr in gj["features"]:
        ftr["geometry"]["coordinates"] = rnd(ftr["geometry"]["coordinates"])
        ftr.pop("id", None)
    t = Transformer.from_crs(3857, 4326, always_xy=True)
    lon0, lat0 = t.transform(minx, miny)
    lon1, lat1 = t.transform(minx + W * res, miny + Hh * res)
    src["ocsge_annees"] = ["2021", y2(dep)]
    data = {"dep": dep, "sources": src, "res_m": res, "bounds": [[lat0, lon0], [lat1, lon1]], "legendes": leg,
            "communes": gj, "indicateurs": ind, "departement": dept}
    (web / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    log(dep, "fini", "OCS GE 2021", dept["stock"]["reference"]["2021"], "MOS", dept["mos"]["urbain_2021"],
        "accord", dept["mos"]["accord_2021"], "flux", dept["flux_brut"]["reference"], dept["mos"]["conso_brute_ha_an"], dept["cerema"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dep")
    ap.add_argument("--etapes", default="prep,classe,web")
    a = ap.parse_args()
    out = PROCESSED / a.dep
    out.mkdir(parents=True, exist_ok=True)
    et = a.etapes.split(",")
    if "prep" in et:
        prep(a.dep, out)
    if "classe" in et:
        classe(a.dep, out)
    if "web" in et:
        web_stats(a.dep, out)
    sys.exit(0)
