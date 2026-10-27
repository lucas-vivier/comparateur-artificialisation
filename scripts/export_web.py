"""Exporte les couches OCS GE d'un département en images web (EPSG:3857) + données JSON.

Usage : python scripts/export_web.py 94 --res 8
Sortie : web/<dep>/  (PNG palettisés, data.json)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio.features
from PIL import Image
from pyproj import Transformer
from rasterio.transform import from_origin

from occsol import territoires
from occsol.nomenclature import classer
from occsol.paths import CONFIG, ROOT, TABLES
from occsol.simulation import preparer, scenarios

TRANSP = (0, 0, 0)


def hexrgb(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def save_png(arr: np.ndarray, palette: list[tuple[int, int, int]], path: Path):
    img = Image.fromarray(arr.astype(np.uint8), mode="P")
    flat = [c for rgb in palette for c in rgb]
    img.putpalette(flat + [0] * (768 - len(flat)))
    img.info["transparency"] = 0
    img.save(path, optimize=True, transparency=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dep")
    ap.add_argument("--res", type=float, default=8.0)
    a = ap.parse_args()
    dep, res = a.dep, a.res
    out = ROOT / "web" / dep
    out.mkdir(parents=True, exist_ok=True)

    nom = pd.read_csv(CONFIG / "nomenclature_ocsge.csv", sep=";")
    cs = nom[nom.CODE.str.startswith("CS")].reset_index(drop=True)
    us = nom[nom.CODE.str.startswith("US")].reset_index(drop=True)
    sc = {r.nom: r for r in scenarios(["reference", "sans_herbace"])}

    g24, t24 = preparer(dep, "2024")
    g21, t21 = preparer(dep, "2021")
    c24 = classer(g24, sc["reference"], t24).to_crs(3857)
    c24h = classer(g24, sc["sans_herbace"], t24).to_crs(3857)
    c21 = classer(g21, sc["reference"], t21).to_crs(3857)

    minx, miny, maxx, maxy = c24.total_bounds
    minx, miny = np.floor(minx / res) * res, np.floor(miny / res) * res
    W, H = int(np.ceil((maxx - minx) / res)), int(np.ceil((maxy - miny) / res))
    tr = from_origin(minx, miny + H * res, res, res)
    print(f"grille {W} x {H} = {W*H/1e6:.1f} Mpx")

    def rast(gdf, vals):
        return rasterio.features.rasterize(zip(gdf.geometry, vals), out_shape=(H, W),
                                           transform=tr, fill=0, dtype="uint8")

    layers = {}
    # Couverture et usage 2024
    csi = {c: i + 1 for i, c in enumerate(cs.CODE)}
    usi = {c: i + 1 for i, c in enumerate(us.CODE)}
    c21_ = classer(g21, sc["reference"], t21).to_crs(3857)
    for key, codes, idx, col, src in [("couverture_2024", cs, csi, "code_cs", c24), ("usage_2024", us, usi, "code_us", c24),
                                      ("couverture_2021", cs, csi, "code_cs", c21_)]:
        arr = rast(src, src[col].map(idx).fillna(0).astype(int))
        pal = [TRANSP] + [tuple(x) for x in codes[["R", "V", "B"]].to_numpy()]
        save_png(arr, pal, out / f"{key}.png")
        present = sorted(set(np.unique(arr)) - {0})
        layers[key] = [{"code": codes.CODE[i - 1], "label": codes.LIBELLE[i - 1].strip(),
                        "color": hexrgb(*pal[i])} for i in present]

    ART = [(0, 0, 0), (227, 234, 229), (200, 69, 47)]  # charte NAC  # 1 non artif, 2 artif
    artif_leg = [{"code": "0", "label": "Non artificialisé", "color": hexrgb(*ART[1])},
                 {"code": "1", "label": "Artificialisé", "color": hexrgb(*ART[2])}]
    a24 = rast(c24, np.where(c24.artif, 2, 1))
    a24h = rast(c24h, np.where(c24h.artif, 2, 1))
    a21 = rast(c21, np.where(c21.artif, 2, 1))
    for key, arr in [("artif_2024_ref", a24), ("artif_2024_sans_herbace", a24h), ("artif_2021_ref", a21)]:
        save_png(arr, ART, out / f"{key}.png")
        layers[key] = artif_leg

    # Évolution 2021 -> 2024 (référence)
    ev = np.zeros_like(a24)
    ev[(a21 == 1) & (a24 == 1)] = 1
    ev[(a21 == 2) & (a24 == 2)] = 2
    ev[(a21 == 1) & (a24 == 2)] = 3
    ev[(a21 == 2) & (a24 == 1)] = 4
    EV = [(0, 0, 0), (238, 242, 239), (214, 211, 220), (200, 69, 47), (41, 114, 84)]
    save_png(ev, EV, out / "evolution_2021_2024.png")
    layers["evolution_2021_2024"] = [
        {"code": "1", "label": "Non artificialisé (stable)", "color": hexrgb(*EV[1])},
        {"code": "2", "label": "Artificialisé (stable)", "color": hexrgb(*EV[2])},
        {"code": "3", "label": "Nouvellement artificialisé", "color": hexrgb(*EV[3])},
        {"code": "4", "label": "Désartificialisé", "color": hexrgb(*EV[4])}]

    # Effet du seuillage 2024
    sv = rast(c24, np.select([c24.bascule & c24.artif, c24.bascule & ~c24.artif, c24.artif],
                             [3, 4, 2], 1))
    SV = [(0, 0, 0), (238, 242, 239), (214, 211, 220), (200, 69, 47), (0, 0, 145)]
    save_png(sv, SV, out / "seuillage_2024.png")
    layers["seuillage_2024"] = [
        {"code": "1", "label": "Non artificialisé", "color": hexrgb(*SV[1])},
        {"code": "2", "label": "Artificialisé", "color": hexrgb(*SV[2])},
        {"code": "3", "label": "Basculé en artificialisé (< 2 500 m²)", "color": hexrgb(*SV[3])},
        {"code": "4", "label": "Basculé en non artificialisé (< 2 500 m²)", "color": hexrgb(*SV[4])}]

    # Emprise en WGS84
    t = Transformer.from_crs(3857, 4326, always_xy=True)
    lon0, lat0 = t.transform(minx, miny)
    lon1, lat1 = t.transform(minx + W * res, miny + H * res)

    # Communes + indicateurs
    com = territoires.communes(dep).to_crs(4326)
    com["geometry"] = com.geometry.simplify(0.00006, preserve_topology=True)
    st = pd.read_csv(TABLES / f"stocks_{dep}.csv", dtype={"insee": str})
    fl = pd.read_csv(TABLES / f"flux_{dep}.csv", dtype={"insee": str})
    ind = {}
    for insee, d in st.groupby("insee"):
        f = fl[fl.insee == insee]
        ind[insee] = {
            "surface_ha": round(float(d.surface_ha.iloc[0]), 1),
            "stock": {s: {str(m): round(float(v), 1) for m, v in zip(x.millesime, x.artif_ha)}
                      for s, x in d.groupby("scenario")},
            "flux": {s: {p: round(float(v), 2) for p, v in zip(x.periode, x.ha_an)}
                     for s, x in f.groupby("scenario")},
        }
    dept = {
        "surface_ha": round(float(st[(st.scenario == "reference") & (st.millesime == 2024)].surface_ha.sum()), 0),
        "stock": st.groupby(["scenario", "millesime"]).artif_ha.sum().round(0)
                   .unstack().rename(columns=str).to_dict("index"),
        "flux": fl.groupby(["scenario", "periode"]).ha_an.sum().round(1).unstack().to_dict("index"),
    }
    gj = json.loads(com[["insee", "nom", "geometry"]].to_json(to_wgs84=False))
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]
    for ftr in gj["features"]:
        ftr["geometry"]["coordinates"] = rnd(ftr["geometry"]["coordinates"])
        ftr.pop("id", None)
    data = {"dep": dep, "res_m": res, "bounds": [[lat0, lon0], [lat1, lon1]],
            "legendes": layers, "communes": gj, "indicateurs": ind, "departement": dept}
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for p in sorted(out.iterdir()):
        print(f"{p.name:32} {p.stat().st_size/1e6:6.2f} Mo")


if __name__ == "__main__":
    main()
