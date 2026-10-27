"""Téléchargement de l'OCS GE depuis le service ATOM de la Géoplateforme IGN.

Flux : https://data.geopf.fr/telechargement/resource/OCSGE?zone=D0XX
Chaque entrée = un produit (millésime, différentiel, patch correctif) livré en .7z.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import py7zr
import requests

from .paths import RAW_OCSGE

ROOT_URL = "https://data.geopf.fr/telechargement/resource"

# Ressources utiles sur la Géoplateforme (vérifié le 20/10/2026) :
RESSOURCES = {
    "ocsge": "OCSGE",                                   # couverture x usage
    "artif": "OCSGE-ARTIFICIALISATION",                 # couche officielle artificialisé / non
    "artif_exemptions": "OCSGE-ARTIFICIALISATION-EXEMPTIONS",  # avec exemptions (parcs, PV)
    "pv": "OCSGE-PV",                                   # panneaux photovoltaïques
}
NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass
class Produit:
    nom: str          # ex. OCS-GE_2-0__GPKG_LAMB93_D094_2021-01-01
    kind: str         # "millesime" | "diff" | "patch"
    zone: str         # ex. D094
    annee: str | None  # millésime (ex. 2021) ou période (ex. 2021-2024)
    feed_url: str
    ressource: str = "ocsge"


def _zone(dep: str) -> str:
    dep = dep.upper().removeprefix("D")
    return f"D{dep.zfill(3)}"


def lister(dep: str, ressource: str = "ocsge") -> list[Produit]:
    """Liste les produits disponibles pour un département (ex. '94', '2A').

    ressource : clé de RESSOURCES ("ocsge", "artif", "artif_exemptions", "pv").
    """
    zone = _zone(dep)
    url = f"{ROOT_URL}/{RESSOURCES.get(ressource, ressource)}"
    r = requests.get(url, params={"zone": zone}, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for link in root.iter("{http://www.w3.org/2005/Atom}link"):
        title = link.get("title", "")
        if zone not in title or link.get("rel") != "alternate":
            continue
        if "_DIFF-" in title:
            kind, annee = "diff", re.search(r"DIFF-(\d{4}-\d{4})", title).group(1)
        elif "PATCHCORRECTIF" in title:
            kind, annee = "patch", re.search(r"_(\d{4})-\d{2}-\d{2}$", title).group(1)
        else:
            kind, annee = "millesime", re.search(r"_(\d{4})-\d{2}-\d{2}$", title).group(1)
        out.append(Produit(title, kind, zone, annee, link.get("href"), ressource))
    return out


def obtenir(dep: str, ressource: str = "ocsge", kind: str = "millesime", annee: str | None = None) -> Path:
    """Raccourci : télécharge (si besoin) le produit voulu et renvoie son dossier."""
    ps = [p for p in lister(dep, ressource) if p.kind == kind and (annee is None or p.annee == annee)]
    if not ps:
        raise LookupError(f"Aucun produit {ressource}/{kind}/{annee} pour {dep}")
    return telecharger(ps[-1])


def _archive_url(p: Produit) -> str:
    r = requests.get(p.feed_url, timeout=60)
    r.raise_for_status()
    for link in ET.fromstring(r.content).iter("{http://www.w3.org/2005/Atom}link"):
        href = link.get("href", "")
        if href.endswith(".7z"):
            return href
    raise RuntimeError(f"Pas d'archive .7z pour {p.nom}")


def telecharger(p: Produit, dest: Path | None = None, force: bool = False) -> Path:
    """Télécharge et décompresse un produit. Retourne le dossier extrait."""
    dest = dest or RAW_OCSGE / p.ressource
    dest.mkdir(parents=True, exist_ok=True)
    out_dir = dest / p.nom
    if out_dir.exists() and not force and any(out_dir.rglob("*.gpkg")):
        return out_dir
    archive = dest / f"{p.nom}.7z"
    if force or not archive.exists():
        with requests.get(_archive_url(p), stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = archive.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.rename(archive)
    with py7zr.SevenZipFile(archive) as z:
        z.extractall(out_dir)
    return out_dir


def gpkg(out_dir: Path, nom: str | None = None) -> Path:
    """Chemin d'un GeoPackage dans un dossier extrait (par défaut OCCUPATION_SOL s'il existe)."""
    files = sorted(out_dir.rglob("*.gpkg"))
    pref = [f for f in files if f.stem == (nom or "OCCUPATION_SOL")]
    files = pref or files
    if not files:
        raise FileNotFoundError(out_dir)
    return files[0]
