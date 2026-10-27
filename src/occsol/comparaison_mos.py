"""Comparaison OCS GE / MOS Île-de-France — EN ATTENTE DES DONNÉES MOS.

Principe prévu :
1. charger le MOS (79 postes, 1 dimension) déposé dans data/raw/mos/ ;
2. le traduire en statut ENAF / artificialisé via config/passage_mos.yaml (à écrire :
   la table de passage n'est pas encore établie) ;
3. comparer avec l'OCS GE sur une même géographie :
   - agrégats par commune / EPCI (stocks, flux) ;
   - accord spatial par intersection des polygones (matrice de confusion en surface).

Attention : le MOS mesure d'abord l'ENAF, l'OCS GE l'artificialisation ; les millésimes
diffèrent (MOS 2017, 2021, 2025 ; OCS GE 94 : 2018, 2021, 2024). À aligner avant toute
lecture des écarts.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .paths import RAW_MOS


def charger_mos(fichier: str, couche: str | None = None) -> gpd.GeoDataFrame:
    return gpd.read_file(RAW_MOS / fichier, layer=couche, engine="pyogrio").to_crs(2154)


def matrice_confusion(a: gpd.GeoDataFrame, col_a: str, b: gpd.GeoDataFrame, col_b: str) -> pd.DataFrame:
    """Surface (ha) croisée entre deux classifications, par intersection géométrique."""
    x = gpd.overlay(a[[col_a, "geometry"]], b[[col_b, "geometry"]], how="intersection",
                    keep_geom_type=True)
    x["ha"] = x.area / 1e4
    return x.pivot_table(index=col_a, columns=col_b, values="ha", aggfunc="sum", fill_value=0)
