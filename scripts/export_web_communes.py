"""Image d'index des communes (même grille que les cartes web) pour les comparaisons dans le navigateur.

Pixel = rang de la commune dans data.json (1..n), 0 = hors département. Usage : python scripts/export_web_communes.py 94
"""
import json
import sys

import numpy as np
import rasterio.features
from pyproj import Transformer
from rasterio.transform import from_origin

from occsol import territoires
from occsol.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from export_web import save_png  # noqa: E402

dep = sys.argv[1]
out = ROOT / "web" / dep
data = json.loads((out / "data.json").read_text())
(lat0, lon0), (lat1, lon1) = data["bounds"]
t = Transformer.from_crs(4326, 3857, always_xy=True)
minx, miny = t.transform(lon0, lat0)
maxx, maxy = t.transform(lon1, lat1)
res = data["res_m"]
W, H = round((maxx - minx) / res), round((maxy - miny) / res)
com = territoires.communes(dep).to_crs(3857).set_index("insee")
order = [f["properties"]["insee"] for f in data["communes"]["features"]]
arr = rasterio.features.rasterize(((com.geometry[c], i) for i, c in enumerate(order, 1)),
                                  out_shape=(H, W), transform=from_origin(minx, maxy, res, res), fill=0, dtype="uint8")
rng = np.random.default_rng(0)
pal = [(0, 0, 0)] + [(i, 0, 0) for i in range(1, len(order) + 1)]  # rouge = rang : lecture exacte dans le navigateur
save_png(arr, pal, out / "communes_idx.png")
print(W, H, len(order), (out / "communes_idx.png").stat().st_size)
