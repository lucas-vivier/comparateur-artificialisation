"""Lecture des couches."""
from __future__ import annotations

import geopandas as gpd

from . import download as dl


def ocsge(dep: str, annee: str) -> gpd.GeoDataFrame:
    """Couche OCCUPATION_SOL d'un millésime (téléchargée si besoin)."""
    return gpd.read_file(dl.gpkg(dl.obtenir(dep, "ocsge", "millesime", annee)), engine="pyogrio")


def artif_officiel(dep: str, annee: str) -> gpd.GeoDataFrame:
    """Couche officielle OCSGE-ARTIFICIALISATION (artif, crit_seuil)."""
    d = dl.obtenir(dep, "artif", "millesime", annee)
    gdf = gpd.read_file(dl.gpkg(d), engine="pyogrio")
    gdf["artif_officiel"] = gdf["artif"].eq("artif")
    return gdf
