"""Simulations : même donnée OCS GE, plusieurs définitions de l'artificialisation."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import yaml

from . import indicateurs, io, territoires
import numpy as np

from .nomenclature import Regle, classer, topologie
from .paths import CONFIG, PROCESSED


def scenarios(noms: list[str] | None = None) -> list[Regle]:
    ref = Regle.reference()
    conf = yaml.safe_load((CONFIG / "scenarios.yaml").read_text())
    out = []
    for nom, kw in conf.items():
        if noms and nom not in noms:
            continue
        kw = {k: tuple(v) if isinstance(v, list) else v for k, v in (kw or {}).items()}
        out.append(ref.variante(nom, **kw))
    return out


def preparer(dep: str, annee: str) -> tuple[gpd.GeoDataFrame, tuple]:
    """Couche OCS GE d'un millésime rattachée aux communes, et sa topologie (en cache)."""
    cache = PROCESSED / f"ocsge_{dep}_{annee}_v2.parquet"  # v2 : polygones découpés par commune
    ctopo = PROCESSED / f"topo_{dep}_{annee}_v2.npz"
    if cache.exists() and ctopo.exists():
        z = np.load(ctopo)
        return gpd.read_parquet(cache), (z["i"], z["j"], z["bord"])
    gdf = io.ocsge(dep, annee)[["id", "code_cs", "code_us", "geometry"]].reset_index(drop=True)
    gdf = territoires.decouper(gdf, territoires.communes(dep))
    topo = topologie(gdf)
    cache.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(cache)
    np.savez_compressed(ctopo, i=topo[0], j=topo[1], bord=topo[2])
    return gdf, topo


def simuler(dep: str, annees: list[str], noms: list[str] | None = None,
            par: str = "insee") -> pd.DataFrame:
    """Stock artificialisé par scénario x millésime x territoire (format long)."""
    res = []
    couches = {a: preparer(dep, a) for a in annees}
    for r in scenarios(noms):
        for a, (gdf, topo) in couches.items():
            c = classer(gdf, r, topo)
            s = indicateurs.stock(c, par=par).reset_index()
            s["scenario"], s["millesime"] = r.nom, int(a)
            res.append(s)
    return pd.concat(res, ignore_index=True)


def flux_scenarios(stocks: pd.DataFrame, par: str = "insee") -> pd.DataFrame:
    """Artificialisation nette entre millésimes successifs, par scénario."""
    w = stocks.pivot_table(index=["scenario", par], columns="millesime", values="artif_ha")
    ans = sorted(w.columns)
    out = []
    for a0, a1 in zip(ans, ans[1:]):
        f = (w[a1] - w[a0]).rename("artif_nette_ha").reset_index()
        f["periode"], f["ha_an"] = f"{a0}-{a1}", f["artif_nette_ha"] / (a1 - a0)
        out.append(f)
    return pd.concat(out, ignore_index=True)
