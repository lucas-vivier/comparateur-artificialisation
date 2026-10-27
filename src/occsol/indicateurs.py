"""Stocks et flux d'artificialisation par territoire."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd


def stock(gdf: gpd.GeoDataFrame, par: str | list[str] | None = "insee", col: str = "artif") -> pd.DataFrame:
    """Surface totale, artificialisée (ha) et part, par territoire."""
    d = pd.DataFrame({"ha": gdf.area / 1e4, "artif": gdf[col]})
    keys = [par] if isinstance(par, str) else (par or [])
    if keys:
        for k in keys:
            d[k] = gdf[k].values
        g = d.groupby(keys)
    else:
        g = d.assign(_t="total").groupby("_t")
    out = pd.DataFrame({
        "surface_ha": g["ha"].sum(),
        "artif_ha": g.apply(lambda x: x.loc[x["artif"], "ha"].sum(), include_groups=False),
    })
    out["part_artif"] = out["artif_ha"] / out["surface_ha"]
    return out


def flux(stock_t0: pd.DataFrame, stock_t1: pd.DataFrame, annees: int | None = None) -> pd.DataFrame:
    """Artificialisation nette = différence de stocks (ha, et ha/an si `annees`)."""
    f = pd.DataFrame({"artif_t0": stock_t0["artif_ha"], "artif_t1": stock_t1["artif_ha"]})
    f["artif_nette_ha"] = f["artif_t1"] - f["artif_t0"]
    if annees:
        f["artif_nette_ha_an"] = f["artif_nette_ha"] / annees
    return f
