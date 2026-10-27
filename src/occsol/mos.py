"""MOS Île-de-France (Institut Paris Region) : téléchargement et nomenclature.

Source : service ArcGIS « Occupation du sol 2025 & 2021 en 79 postes de la région Île-de-France »
https://geoweb.iau-idf.fr/agsmap1/rest/services/OPENDATA/OpendataIAU4/MapServer/25
Licence ouverte (Institut Paris Region). Champs : mos2021, mos2025 (codes 1-79), insee.
Version de février 2026 ; l'IPR annonce des mises à jour deux fois par an (les dates
antérieures peuvent être modifiées).
"""
from __future__ import annotations

import json
import time

import geopandas as gpd
import pandas as pd
import requests

from .paths import CONFIG, RAW_MOS

SERVICE = "https://geoweb.iau-idf.fr/agsmap1/rest/services/OPENDATA/OpendataIAU4/MapServer/25"


def telecharger(dep: str, force: bool = False) -> gpd.GeoDataFrame:
    """Polygones MOS 2021/2025 d'un département d'IDF, en Lambert-93 (mis en cache)."""
    out = RAW_MOS / f"mos_idf_{dep}_2021_2025.parquet"  # parquet : le GPKG (SQLite) échoue sur certains montages réseau
    if out.exists() and not force:
        return gpd.read_parquet(out)
    where = f"insee >= {int(dep)}000 AND insee < {int(dep) + 1}000"
    parts, offset = [], 0
    while True:
        for essai in range(8):  # le service coupe parfois la connexion : on réessaie
            try:
                r = requests.get(f"{SERVICE}/query", params={
                    "where": where, "outFields": "objectid,mos2021,mos2025,insee", "outSR": 2154,
                    "f": "geojson", "resultOffset": offset, "resultRecordCount": 1000,
                    "orderByFields": "objectid"}, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException:
                if essai == 7:
                    raise
                time.sleep(2 + 3 * essai)
        fc = r.json()
        feats = fc.get("features", [])
        if not feats:
            break
        parts.append(gpd.GeoDataFrame.from_features(feats, crs=2154))
        offset += len(feats)
    gdf = pd.concat(parts, ignore_index=True).drop_duplicates("objectid")
    gdf["insee"] = gdf["insee"].astype(int).astype(str)
    RAW_MOS.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out)
    return gdf


def nomenclature() -> pd.DataFrame:
    """Table des 79 postes (config/mos_idf_nomenclature.csv)."""
    return pd.read_csv(CONFIG / "mos_idf_nomenclature.csv", sep=";")
