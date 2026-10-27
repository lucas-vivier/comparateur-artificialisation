"""Parcelles cadastrales Etalab (PCI vecteur) par commune, au format compact pour le comparateur.

Source : https://cadastre.data.gouv.fr/data/etalab-cadastre/<millésime>/geojson/communes/
Licence ouverte. Sortie : web/<dep>/cadastre/<insee>.json
Usage : python scripts/export_web_cadastre.py 94 [--millesime 2026-09-01]
"""
from __future__ import annotations

import argparse
import gzip
import json

import requests

from occsol.paths import RAW, ROOT

BASE = "https://cadastre.data.gouv.fr/data/etalab-cadastre/{m}/geojson/communes/{d}/{c}/cadastre-{c}-parcelles.json.gz"


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 6), round(c[1], 6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dep")
    ap.add_argument("--millesime", default="2026-09-01")
    a = ap.parse_args()
    out = ROOT / "web" / a.dep / "cadastre"
    out.mkdir(parents=True, exist_ok=True)
    cache = RAW / "cadastre" / a.millesime
    cache.mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / "web" / a.dep / "data.json").read_text())
    total = 0
    for f in data["communes"]["features"]:
        c = f["properties"]["insee"]
        gz = cache / f"{c}.json.gz"
        if not gz.exists():
            r = requests.get(BASE.format(m=a.millesime, d=a.dep, c=c), timeout=120)
            r.raise_for_status()
            gz.write_bytes(r.content)
        fc = json.load(gzip.open(gz))
        feats = []
        for p in fc["features"]:
            pr = p["properties"]
            ref = (pr["prefixe"] + " " if pr["prefixe"] != "000" else "") + f'{pr["section"]} {int(pr["numero"])}'
            feats.append({"type": "Feature", "properties": {"r": ref, "c": pr.get("contenance")},
                          "geometry": {"type": p["geometry"]["type"], "coordinates": rnd(p["geometry"]["coordinates"])}})
        js = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
        (out / f"{c}.json").write_text(js)
        total += len(js)
    data["cadastre"] = {"millesime": a.millesime, "source": "Etalab, PCI vecteur (DGFiP)"}
    (ROOT / "web" / a.dep / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(data['communes']['features'])} communes, {total/1e6:.1f} Mo")


if __name__ == "__main__":
    main()
