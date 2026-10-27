"""Variantes de règle OCS GE (statut 2021, évolution 2021-2024) + flux Cerema (Fichiers fonciers).

À lancer après export_web.py et export_web_mos.py. Usage : python scripts/export_web_variantes.py 94
Cerema : CONSOENAF 2011-2025, data.gouv.fr (licence ouverte), valeurs en m² par année au 1er janvier.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import rasterio.features
from pyproj import Transformer
from rasterio.transform import from_origin

from occsol.nomenclature import classer
from occsol.paths import RAW, ROOT
from occsol.simulation import preparer, scenarios

sys.path.insert(0, str(ROOT / "scripts"))
from export_web import save_png  # noqa: E402

H = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
VARIANTES = ["sans_herbace", "seuil_0", "seuil_1000", "seuil_5000"]


def main(dep: str):
    out = ROOT / "web" / dep
    data = json.loads((out / "data.json").read_text())
    (lat0, lon0), (lat1, lon1) = data["bounds"]
    t = Transformer.from_crs(4326, 3857, always_xy=True)
    minx, miny = t.transform(lon0, lat0)
    maxx, maxy = t.transform(lon1, lat1)
    res = data["res_m"]
    W, Hh = round((maxx - minx) / res), round((maxy - miny) / res)
    tr = from_origin(minx, maxy, res, res)
    rast = lambda g, v: rasterio.features.rasterize(zip(g.geometry, v), out_shape=(Hh, W), transform=tr, fill=0, dtype="uint8")  # noqa: E731

    g21, t21 = preparer(dep, "2021")
    g24, t24 = preparer(dep, "2024")
    ART = ["#000000", "#E3EAE5", "#C8452F"]
    EV = ["#000000", "#EEF2EF", "#D6D3DC", "#C8452F", "#297254"]
    for r in scenarios(VARIANTES):
        c21 = classer(g21, r, t21).to_crs(3857)
        c24 = classer(g24, r, t24).to_crs(3857)
        a21 = rast(c21, np.where(c21.artif, 2, 1))
        a24 = rast(c24, np.where(c24.artif, 2, 1))
        save_png(a21, [H(c) for c in ART], out / f"artif_2021_{r.nom}.png")
        ev = np.zeros_like(a24)
        ev[(a21 == 1) & (a24 == 1)] = 1
        ev[(a21 == 2) & (a24 == 2)] = 2
        ev[(a21 == 1) & (a24 == 2)] = 3
        ev[(a21 == 2) & (a24 == 1)] = 4
        save_png(ev, [H(c) for c in EV], out / f"evolution_2021_2024_{r.nom}.png")
        data["legendes"][f"artif_2021_{r.nom}"] = data["legendes"]["artif_2021_ref"]
        data["legendes"][f"evolution_2021_2024_{r.nom}"] = data["legendes"]["evolution_2021_2024"]
        print(r.nom, "ok")

    # Flux bruts OCS GE (surfaces devenues artificialisées / désartificialisées), grille Lambert-93 à 5 m
    from occsol import territoires
    com = territoires.communes(dep)
    x0, y0, x1, y1 = g21.total_bounds
    r5 = 5.0
    W5, H5 = int(np.ceil((x1 - x0) / r5)), int(np.ceil((y1 - y0) / r5))
    tr5 = from_origin(x0, y1, r5, r5)
    r5r = lambda g, v, dt="uint8": rasterio.features.rasterize(zip(g.geometry, v), out_shape=(H5, W5), transform=tr5, fill=0, dtype=dt)  # noqa: E731
    cid = r5r(com, range(1, len(com) + 1), "uint16")
    px = r5 * r5 / 1e4
    for r in scenarios(["reference"] + VARIANTES):
        a = r5r(g21, np.where(classer(g21, r, t21).artif, 2, 1))
        b = r5r(g24, np.where(classer(g24, r, t24).artif, 2, 1))
        gain = np.bincount(cid[(a == 1) & (b == 2)], minlength=len(com) + 1) * px / 3
        perte = np.bincount(cid[(a == 2) & (b == 1)], minlength=len(com) + 1) * px / 3
        for i, insee in enumerate(com.insee, start=1):
            if insee in data["indicateurs"]:
                data["indicateurs"][insee].setdefault("flux_brut", {})[r.nom] = {
                    "artif": round(float(gain[i]), 2), "desartif": round(float(perte[i]), 2)}
        data["departement"].setdefault("flux_brut", {})[r.nom] = {
            "artif": round(float(gain[1:].sum()), 2), "desartif": round(float(perte[1:].sum()), 2)}
    print("flux bruts dep", data["departement"]["flux_brut"]["reference"])

    # Cerema : flux annuels en m² -> ha/an
    cer = pd.read_csv(RAW / "cerema" / "conso_com_2011_2025.csv", dtype={"idcom": str},
                      usecols=["idcom", "naf21art22", "naf22art23", "naf23art24", "naf24art25"])
    cer = cer[cer.idcom.str.startswith(dep)].set_index("idcom")
    f2124 = (cer.naf21art22 + cer.naf22art23 + cer.naf23art24) / 1e4 / 3
    f2125 = (cer.naf21art22 + cer.naf22art23 + cer.naf23art24 + cer.naf24art25) / 1e4 / 4
    for insee, ind in data["indicateurs"].items():
        if insee in cer.index:
            ind["cerema"] = {"2021-2024": round(float(f2124[insee]), 2), "2021-2025": round(float(f2125[insee]), 2)}
    data["departement"]["cerema"] = {"2021-2024": round(float(f2124.sum()), 2), "2021-2025": round(float(f2125.sum()), 2)}
    data["cerema_source"] = "CONSOENAF 2011-2025, Cerema (Fichiers fonciers), data.gouv.fr"
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print("cerema dep", data["departement"]["cerema"], "créteil", data["indicateurs"].get("94028", {}).get("cerema"))


if __name__ == "__main__":
    main(sys.argv[1])
