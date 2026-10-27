"""Ajoute au dossier web/<dep>/ les couches MOS IDF, le croisement OCS GE × MOS et les indicateurs.

À lancer après scripts/export_web.py. Usage : python scripts/export_web_mos.py 94
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import from_origin

from occsol import mos, territoires
from occsol.nomenclature import classer
from occsol.paths import ROOT
from occsol.simulation import preparer, scenarios

sys.path.insert(0, str(ROOT / "scripts"))
from export_web import hexrgb, save_png  # noqa: E402

# Couleurs proches de la légende de l'Institut Paris Region (12 postes), indicatives
COUL12 = {1: "#8FC79A", 2: "#C9BA5B", 3: "#EDE3A0", 4: "#7FC8EE", 5: "#CFE5C9", 6: "#FBC49B",
          7: "#EF7A50", 8: "#D99BC0", 9: "#45BBB2", 10: "#A57DB8", 11: "#B5B5B5", 12: "#8C9474"}
H = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731


def main(dep: str):
    out = ROOT / "web" / dep
    data = json.loads((out / "data.json").read_text())
    nom = mos.nomenclature().set_index("code")
    g = mos.telecharger(dep)
    for a in ("2021", "2025"):
        g[f"g{a}"] = g[f"mos{a}"].map(nom.groupe12).astype(int)
        g[f"naf{a}"] = g[f"mos{a}"].map(nom.enaf).astype(int)

    # --- grille web identique à export_web.py (EPSG:3857) ---
    (lat0, lon0), (lat1, lon1) = data["bounds"]
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 3857, always_xy=True)
    minx, miny = t.transform(lon0, lat0)
    maxx, maxy = t.transform(lon1, lat1)
    res = data["res_m"]
    W, Hh = round((maxx - minx) / res), round((maxy - miny) / res)
    tr = from_origin(minx, maxy, res, res)
    g3 = g.to_crs(3857)

    def rast(gdf, vals, shape=(Hh, W), transform=tr):
        return rasterio.features.rasterize(zip(gdf.geometry, vals), out_shape=shape,
                                           transform=transform, fill=0, dtype="uint8")

    lab12 = nom.drop_duplicates("groupe12").set_index("groupe12").libelle12
    pal12 = [(0, 0, 0)] + [H(COUL12[i]) for i in range(1, 13)]
    for a in ("2021", "2025"):
        arr = rast(g3, g3[f"g{a}"])
        save_png(arr, pal12, out / f"mos_{a}.png")
        data["legendes"][f"mos_{a}"] = [{"code": str(i), "label": lab12[i], "color": COUL12[i]}
                                        for i in sorted(set(np.unique(arr)) - {0})]
    # MOS 2021 en deux classes : ENAF / urbanisé (pendant de l'artificialisation OCS GE)
    bi = rast(g3, np.where(g3.naf2021 == 1, 1, 2))
    save_png(bi, [(0, 0, 0), H("#E3EAE5"), H("#000091")], out / "mos_enaf_2021.png")
    data["legendes"]["mos_enaf_2021"] = [{"code": "1", "label": "ENAF (naturel, agricole, forestier)", "color": "#E3EAE5"},
                                         {"code": "2", "label": "Urbanisé", "color": "#000091"}]
    # Évolution MOS 2021 -> 2025
    ev = rast(g3, np.select([(g3.naf2021 == 1) & (g3.naf2025 == 1), (g3.naf2021 == 0) & (g3.naf2025 == 0),
                             (g3.naf2021 == 1) & (g3.naf2025 == 0)], [1, 2, 3], 4))
    EV = ["#000000", "#EEF2EF", "#D6D3DC", "#C8452F", "#297254"]
    save_png(ev, [H(c) for c in EV], out / "mos_evolution_2021_2025.png")
    data["legendes"]["mos_evolution_2021_2025"] = [
        {"code": "1", "label": "ENAF (stable)", "color": EV[1]},
        {"code": "2", "label": "Urbanisé (stable)", "color": EV[2]},
        {"code": "3", "label": "ENAF consommé", "color": EV[3]},
        {"code": "4", "label": "Retour en ENAF", "color": EV[4]}]

    # Croisement 2021 : OCS GE artificialisé (règle officielle) × MOS urbanisé
    ref = scenarios(["reference"])[0]
    o21, topo = preparer(dep, "2021")
    c21 = classer(o21, ref, topo)
    c21_3 = c21.to_crs(3857)
    a = rast(c21_3, np.where(c21_3.artif, 2, 1))
    m = rast(g3, np.where(g3.naf2021 == 0, 2, 1))
    cr = np.zeros_like(a)
    cr[(a == 1) & (m == 1)] = 1
    cr[(a == 2) & (m == 2)] = 2
    cr[(a == 2) & (m == 1)] = 3
    cr[(a == 1) & (m == 2)] = 4
    CR = ["#000000", "#EEF2EF", "#D6D3DC", "#C8452F", "#000091"]
    save_png(cr, [H(c) for c in CR], out / "croisement_2021.png")
    data["legendes"]["croisement_2021"] = [
        {"code": "1", "label": "Accord : naturel, agricole ou forestier", "color": CR[1]},
        {"code": "2", "label": "Accord : artificialisé et urbanisé", "color": CR[2]},
        {"code": "3", "label": "Artificialisé pour l'OCS GE seulement", "color": CR[3]},
        {"code": "4", "label": "Urbanisé pour le MOS seulement", "color": CR[4]}]

    # --- Indicateurs : polygones MOS + croisement sur une grille Lambert-93 à 5 m ---
    g["ha"] = g.area / 1e4
    com = territoires.communes(dep)
    x0, y0, x1, y1 = com.total_bounds
    r5 = 5.0
    W5, H5 = int(np.ceil((x1 - x0) / r5)), int(np.ceil((y1 - y0) / r5))
    tr5 = from_origin(x0, y1, r5, r5)
    cid = rasterio.features.rasterize(zip(com.geometry, range(1, len(com) + 1)), out_shape=(H5, W5),
                                      transform=tr5, fill=0, dtype="uint16")
    a5 = rast(c21, np.where(c21.artif, 2, 1), (H5, W5), tr5)
    m5 = rast(g, np.where(g.naf2021 == 0, 2, 1), (H5, W5), tr5)
    px = r5 * r5 / 1e4
    ind = data["indicateurs"]

    def bloc(sub, k=None):
        urb21 = sub.loc[sub.naf2021 == 0, "ha"].sum()
        urb25 = sub.loc[sub.naf2025 == 0, "ha"].sum()
        conso = sub.loc[(sub.naf2021 == 1) & (sub.naf2025 == 0), "ha"].sum()
        retour = sub.loc[(sub.naf2021 == 0) & (sub.naf2025 == 1), "ha"].sum()
        sel = (cid == k) if k else (cid > 0)
        both = sel & (a5 > 0) & (m5 > 0)
        n = both.sum()
        return {"urbain_2021": round(float(urb21), 1), "urbain_2025": round(float(urb25), 1),
                "conso_brute_ha_an": round(float(conso) / 4, 2),
                "conso_nette_ha_an": round(float(conso - retour) / 4, 2),
                "accord_2021": round(float(((a5 == m5) & both).sum() / n), 4) if n else None,
                "ocs_seul_ha": round(float(((a5 == 2) & (m5 == 1) & both).sum() * px), 1),
                "mos_seul_ha": round(float(((a5 == 1) & (m5 == 2) & both).sum() * px), 1)}

    for i, insee in enumerate(com.insee, start=1):
        if insee in ind:
            ind[insee]["mos"] = bloc(g[g.insee == insee], i)
    data["departement"]["mos"] = bloc(g)
    data["mos_source"] = {"version": "février 2026", "licence": "Licence ouverte (Institut Paris Region)"}
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(json.dumps(data["departement"]["mos"], ensure_ascii=False))
    for p in sorted(out.glob("*mos*")) + [out / "croisement_2021.png"]:
        print(f"{p.name:32} {p.stat().st_size/1e6:6.2f} Mo")


if __name__ == "__main__":
    main(sys.argv[1])
