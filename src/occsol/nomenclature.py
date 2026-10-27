"""Passage OCS GE (couverture x usage) -> artificialisé, avec seuillage paramétrable.

Les paramètres par défaut reproduisent la règle officielle (config/artificialisation.yaml).
Chaque paramètre peut être modifié pour simuler une autre définition.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from .paths import CONFIG


@dataclass(frozen=True)
class Regle:
    cs_anthropise: tuple[str, ...]
    exceptions_anthropise: tuple[tuple[str, str], ...]
    cs_herbace: tuple[str, ...]
    us_herbace_artif: tuple[str, ...]
    seuil_m2: float = 2500
    bati_protege: bool = True
    cs_bati: str = "CS1.1.1.1"
    nom: str = "reference"

    @classmethod
    def reference(cls) -> "Regle":
        c = yaml.safe_load((CONFIG / "artificialisation.yaml").read_text())["reference"]
        return cls(
            cs_anthropise=tuple(c["cs_anthropise"]),
            exceptions_anthropise=tuple((e["cs"], e["us"]) for e in c["exceptions_anthropise"]),
            cs_herbace=tuple(c["cs_herbace"]),
            us_herbace_artif=tuple(c["us_herbace_artif"]),
            seuil_m2=c["seuil_m2"],
            bati_protege=c["bati_protege"],
            cs_bati=c["cs_bati"],
        )

    def variante(self, nom: str, **kw) -> "Regle":
        return replace(self, nom=nom, **kw)


def classer_brut(df: pd.DataFrame, r: Regle) -> pd.Series:
    """Statut artificialisé avant seuillage (booléen), polygone par polygone."""
    cs, us = df["code_cs"], df["code_us"]
    anthrop = cs.isin(r.cs_anthropise)
    for e_cs, e_us in r.exceptions_anthropise:
        anthrop &= ~((cs == e_cs) & (us == e_us))
    herb = cs.isin(r.cs_herbace) & us.isin(r.us_herbace_artif)
    return anthrop | herb


def adjacence(geom, seuil_sommets: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Paires (i, j), i < j, de polygones qui se touchent ou se recouvrent.

    Les très gros polygones (mer, grands massifs) rendent le test « intersects » très lent quand ils
    sont candidats non préparés. On les traite donc toujours comme géométries d'entrée (préparées) :
    gros -> tous, et petits -> petits.
    """
    import shapely

    g = np.asarray(geom)
    n = shapely.get_num_coordinates(g)
    gros = n > seuil_sommets
    ig, ip = np.flatnonzero(gros), np.flatnonzero(~gros)
    tree_all = shapely.STRtree(g)
    a1, b1 = tree_all.query(g[ig], predicate="intersects")
    a1 = ig[a1]
    tree_p = shapely.STRtree(g[ip])
    a2, b2 = tree_p.query(g[ip], predicate="intersects")
    a2, b2 = ip[a2], ip[b2]
    i = np.concatenate([a1, a2]); j = np.concatenate([b1, b2])
    lo, hi = np.minimum(i, j), np.maximum(i, j)
    k = lo < hi
    paires = np.unique(np.stack([lo[k], hi[k]], axis=1), axis=0)
    return paires[:, 0], paires[:, 1]


def topologie(gdf: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcule une fois par couche : arêtes d'adjacence (i, j) et polygones au bord de l'emprise.

    Indépendant du scénario : à mettre en cache (voir `classer(..., topo=...)`).
    """
    geom = gdf.geometry.reset_index(drop=True)
    tree = geom.sindex
    i, j = tree.query(geom, predicate="intersects")
    keep = i < j
    bord = geom.intersects(geom.union_all().boundary).to_numpy()
    return i[keep], j[keep], bord


def seuiller(gdf: gpd.GeoDataFrame, brut: pd.Series, r: Regle,
             topo: tuple | None = None, max_iter: int = 20) -> tuple[pd.Series, pd.Series]:
    """Applique le seuillage. Retourne (statut final, bascule).

    Méthode (approximation de la fiche p. 4-7) : on regroupe les polygones contigus de même
    statut ; tout groupe de moins de `seuil_m2` qui ne touche pas la limite de l'emprise est
    entouré de l'autre statut et bascule. Avec `bati_protege`, un groupe artificialisé
    contenant du bâti ne bascule pas. Les passages sont répétés jusqu'à ce que plus rien ne
    bascule (`max_iter` passages au plus ; `max_iter=1` = ancien calcul en un seul passage).
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = len(gdf)
    if not r.seuil_m2:
        return brut.copy(), pd.Series(False, index=gdf.index)
    i, j, bord = topo if topo is not None else topologie(gdf)
    aires = gdf.area.to_numpy()
    est_cs_bati = gdf["code_cs"].to_numpy() == r.cs_bati
    s0 = brut.to_numpy().astype(bool)
    s = s0.copy()
    for _ in range(max_iter):
        m = s[i] == s[j]
        adj = coo_matrix((np.ones(m.sum()), (i[m], j[m])), shape=(n, n))
        _, lab = connected_components(adj, directed=False)
        aire = np.bincount(lab, weights=aires)
        au_bord = np.bincount(lab, weights=bord.astype(float)) > 0
        bati = np.zeros(len(aire), bool)
        if r.bati_protege:
            bati = np.bincount(lab, weights=(est_cs_bati & s).astype(float)) > 0
        flip = ((aire < r.seuil_m2) & ~au_bord & ~bati)[lab]
        if not flip.any():
            break
        s = s ^ flip
    bascule = pd.Series(s != s0, index=gdf.index)
    return pd.Series(s, index=gdf.index), bascule


def classer(gdf: gpd.GeoDataFrame, r: Regle | None = None, topo: tuple | None = None) -> gpd.GeoDataFrame:
    """Ajoute les colonnes artif_brut, artif, bascule à une couche OCS GE."""
    r = r or Regle.reference()
    out = gdf.copy()
    out["artif_brut"] = classer_brut(out, r)
    out["artif"], out["bascule"] = seuiller(out, out["artif_brut"], r, topo)
    return out
