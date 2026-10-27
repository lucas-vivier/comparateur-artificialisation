"""Extrait du MOS foncier breton (zip régional) les polygones d'un ou plusieurs départements -> parquet.

Usage : python scripts/extraire_mos_bzh.py 29 22
Lecture par emprise (index spatial) puis filtre sur le code commune, un département à la fois.
"""
import sys
import time

import geopandas as gpd
import pyogrio

from occsol.paths import RAW

SRC = RAW / "bzh" / "mos_foncier_bretagne_maj.gpkg"  # décompressé depuis mos_foncier_2011_2021_2024_bretagne.zip
sys.path.insert(0, str(RAW.parent.parent / "scripts"))
from pipeline_dep import communes  # noqa: E402

cols = ["code4_2011", "code4_2021", "code4_2024", "enaf_2021", "enaf_2024", "CODGEO_2025"]
N = 250000  # par morceaux : un département dépasse la mémoire en une seule lecture
for d in sys.argv[1:]:
    t = time.time()
    bb = tuple(communes(d).total_bounds)
    out = RAW / "bzh" / f"mos_bzh_{d}"
    out.mkdir(exist_ok=True)
    off, n, k = 0, 0, 0
    while True:
        df = pyogrio.read_dataframe(SRC, columns=cols, bbox=bb, where=f"CODGEO_2025 LIKE '{d}%'",
                                    skip_features=off, max_features=N)
        if df.empty:
            break
        df.to_parquet(out / f"part_{k:03d}.parquet")
        k += 1
        off += len(df); n += len(df)
        print(d, off, round(time.time() - t), "s", flush=True)
        del df
    print(d, "fini", n, "polygones", round(time.time() - t), "s", flush=True)
