# occupation-sol : comparateur d'artificialisation

Code de la NAC INSP (sujet IGN n° 2) : comparer les mesures d'occupation du sol (OCS GE, MOS, OCS2D,
Fichiers fonciers) et simuler l'effet des choix de méthode sur l'artificialisation mesurée.

**Comparateur en ligne** : https://lucas-vivier.github.io/comparateur-artificialisation/

Prototype de travail, non validé par les producteurs de données (IGN, Institut Paris Region,
Région Hauts-de-France, Région Bretagne, Cerema).

## Le comparateur (dossier `web/`)

Site statique, sans serveur : `web/index.html` lit pour chaque département `web/<dép>/data.json`,
`details.json` et des cartes PNG. Publication automatique sur GitHub Pages à chaque push sur `main`
qui touche `web/` (`.github/workflows/pages.yml`).

- **15 départements avec base régionale** : Île-de-France (MOS), Hauts-de-France (OCS2D),
  Finistère et Côtes-d'Armor (MOS foncier breton). Deux cartes côte à côte, OCS GE et base régionale.
- **81 autres départements** : OCS GE face aux Fichiers fonciers seulement, sur les deux derniers
  millésimes OCS GE de chaque département ; cartes allégées.
- Parcelles cadastrales : Val-de-Marne seulement (`web/94/cadastre/`).

Tester en local (le site ne s'ouvre pas en double-cliquant, il faut un petit serveur) :

```bash
cd web && python3 -m http.server 8000   # puis http://localhost:8000
```

`web/comparateur_template.html` est une ancienne version de la page, gardée pour mémoire ;
la page publiée est `web/index.html`.

## Installation du code

```bash
uv sync --extra dev          # crée .venv et installe le paquet occsol
uv run occsol --help
```

## Arborescence

```
config/
  artificialisation.yaml   règle officielle OCS GE -> artificialisé (référence)
  scenarios.yaml           variantes à simuler (seuil, herbacé, bâti)
  nomenclature_ocsge.csv   codes CS / US (livrés par l'IGN)
  mos_*_nomenclature.csv   nomenclatures MOS Île-de-France et Bretagne
src/occsol/
  download.py              service ATOM Géoplateforme (OCSGE, OCSGE-ARTIFICIALISATION, …)
  io.py                    lecture des couches
  nomenclature.py          classement CS x US + seuillage paramétrable
  territoires.py           communes (geo.api.gouv.fr) et rattachement
  indicateurs.py           stocks, flux
  simulation.py            boucle scénarios x millésimes
  mos.py, comparaison_mos.py
  cli.py                   ligne de commande
scripts/
  pipeline_dep.py, export_web*.py      départements avec base régionale
  france_dep.py, france_boucle.sh, france_bilan.py   81 autres départements
  piste_*.py                           analyses des écarts
data/                      données brutes et caches (non versionnés, à retélécharger)
outputs/tables, pistes     résultats et notes d'analyse
web/                       le comparateur publié
tests/                     pytest
```

## Commandes

```bash
occsol lister 94 --ressource artif        # produits disponibles
occsol valider 94 2021                    # règle recalculée vs couche officielle
occsol simuler 94 --annees 2018,2021,2024 # -> outputs/tables/stocks_94.csv, flux_94.csv
```

## Ce qui est vérifié

- **Règle de classement** : reproduit la couche officielle `OCSGE-ARTIFICIALISATION`
  à 99,97 % de la surface (Val-de-Marne, 2021 ; 18 330 ha recalculés contre 18 334 ha).
  Avant seuillage, l'accord est de 100 %. L'écart restant vient du seuillage, approché ici
  en un seul passage.
- **Non couvert** : exemptions du décret 2023-1096 (parcs et jardins publics, PV au sol),
  disponibles dans la ressource `OCSGE-ARTIFICIALISATION-EXEMPTIONS` ; elles ne sont affichées
  que pour les 15 départements avec base régionale.

## Données et licences

| Source | Producteur | Usage ici |
|---|---|---|
| OCS GE 2.0 | IGN | cartes et indicateurs, 96 départements |
| MOS 2021-2025 | Institut Paris Region | Île-de-France |
| OCS2D (couche ENAF) | Région Hauts-de-France | Hauts-de-France |
| MOS foncier | Région Bretagne | Finistère, Côtes-d'Armor |
| Consommation d'ENAF 2011-2025 (Fichiers fonciers) | Cerema | rythmes, 96 départements |
| PCI vecteur (parcelles) | Etalab / DGFiP | Val-de-Marne |
| Contours communaux | geo.api.gouv.fr | 96 départements |

Les fichiers de `web/` et `outputs/` sont des données dérivées de ces sources, diffusées sous
licences ouvertes ; toute réutilisation doit citer les producteurs. Le code est sous licence MIT
(voir `LICENSE`).
