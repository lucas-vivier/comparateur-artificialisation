"""Contours communaux (API Découpage administratif, geo.api.gouv.fr)."""
from __future__ import annotations

import geopandas as gpd
import requests

from .paths import RAW


def communes(dep: str) -> gpd.GeoDataFrame:
    """Communes d'un département en Lambert-93, mises en cache dans data/raw/communes/.

    Contours de l'API geo.api.gouv.fr (issus d'ADMIN EXPRESS, possiblement généralisés) :
    suffisant pour rattacher des polygones par point intérieur, pas pour des calculs de bord.
    """
    cache = RAW / "communes" / f"communes_{dep}.geojson"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://geo.api.gouv.fr/departements/{dep}/communes"
        r = requests.get(url, params={"format": "geojson", "geometry": "contour",
                                      "fields": "code,nom,codeEpci"}, timeout=60)
        r.raise_for_status()
        cache.write_bytes(r.content)
    return gpd.read_file(cache).to_crs(2154).rename(columns={"code": "insee"})


def rattacher(gdf: gpd.GeoDataFrame, com: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ajoute insee / nom à chaque polygone (point intérieur dans la commune)."""
    pts = gpd.GeoDataFrame(geometry=gdf.geometry.representative_point(), index=gdf.index, crs=gdf.crs)
    j = gpd.sjoin(pts, com[["insee", "nom", "geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated()]
    out = gdf.copy()
    out["insee"], out["nom_commune"] = j["insee"], j["nom"]
    return out


def decouper(gdf: gpd.GeoDataFrame, com: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Découpe les polygones par les limites communales (les polygones OCS GE les traversent).

    Les morceaux hors des contours communaux sont gardés (insee vide) pour conserver la surface totale.
    """
    out = gpd.overlay(gdf, com[["insee", "nom", "geometry"]].rename(columns={"nom": "nom_commune"}),
                      how="identity", keep_geom_type=True)
    return out.explode(index_parts=False).reset_index(drop=True)
