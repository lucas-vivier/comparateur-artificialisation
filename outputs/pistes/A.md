# Piste A — Validation du recalcul contre les couches officielles IGN

*21/10/2026. Scripts : `scripts/piste_A_lister.py`, `piste_A_telecharger.sh`, `piste_A_comparer.py`, `piste_A_run.sh`, `piste_A_tableau.py`.
Tables : `outputs/tables/piste_A_validation_ign.csv` (13 départements + IDF, HdF, ensemble), `outputs/tables/piste_A_validation_ign_communes.csv` (5 048 communes), détail brut dans `outputs/tables/piste_A/`.*

## 1. Ressources IGN récupérées

J'ai interrogé l'API de téléchargement de la Géoplateforme (`/telechargement/resource/<ressource>?zone=D0xx`). Le catalogue complet est dans `data/raw/ign_artif/catalogue.csv`. Les archives .7z sont rangées dans `data/raw/ign_artif/` et ne sont pas décompressées, faute de place disque. Le script `piste_A_comparer.py` les extrait au besoin dans un dossier temporaire.

| sous-dossier | ressource Géoplateforme | produit | couverture |
|---|---|---|---|
| `artif/` | OCSGE-ARTIFICIALISATION | millésimes 2021 et 2024 (Nord : 2025) | 13/13 |
| `artif_diff/` | OCSGE-ARTIFICIALISATION (produit `DIFF-2021-2024`, Nord `DIFF-2021-2025`) | couche `zan_evol` : +1 artificialisation / −1 désartificialisation | 13/13 |
| `patch/` | OCSGE (produit `PATCHCORRECTIF … 2021-01-01`) | corrections du millésime 2021 (`cs_corr`, `us_corr`, `RAS` = inchangé) | 13/13 |
| `ocsge_diff/` | OCSGE (produit `DIFF-2021-2024/2025`) | changements de couverture et d'usage | 13/13, non exploité au final |

- Il n'existe pas de ressource distincte nommée « OCSGE-ARTIFICIALISATION-DIFF » : le différentiel est publié comme un produit de la ressource OCSGE-ARTIFICIALISATION.
- Aucun patch correctif n'est publié pour les millésimes 2024 et 2025. Il n'y a pas non plus de « millésime corrigé » : seul le patch 2021 existe.
- Constat (vérifié sur Paris) : la couche ARTIFICIALISATION 2021 et le DIFF `zan_evol` portent les codes **non corrigés** du millésime 2021. Seuls 2 polygones sur 1 013 corrigés reprennent le code du patch. Les codes `cs_2021` du DIFF sont identiques à 100 % aux codes bruts. Sur les 13 départements, le DIFF IGN est égal à la différence des deux millésimes IGN (colonnes `ign_millesimes_*` = `ign_diff_*`, à 0,1 ha/an près). **Les flux officiels incluent donc les corrections du millésime 2021.**

## 2. Recalcul (variante reference) contre IGN

Méthode : la couche IGN est rastérisée sur la grille de `pipeline_dep.py` (pas de 5, 10 ou 15 m, avec le même index communal). Les écarts ne viennent donc que de la classification. Les valeurs recalculées retrouvent celles de `data.json` (écart maximal par commune : 0,05 ha de stock, 0,005 ha/an de flux). En complément, j'ai fait une comparaison vectorielle exacte en joignant les polygones par identifiant. Tous les identifiants se retrouvent des deux côtés.

| | stock 2021 recalculé (ha) | stock 2021 IGN (ha) | écart | artif. recalc. / IGN (ha/an) | désartif. recalc. / IGN (ha/an) |
|---|---|---|---|---|---|
| IDF (8 dép.) | 252 500 | 252 568 | −68 ha (−0,03 %) | 1 185,7 / 1 185,6 | 279,0 / 279,1 |
| HdF (5 dép.) | 359 952 | 359 964 | −12 ha (−0,003 %) | 2 154,0 / 2 154,2 | 683,5 / 683,8 |
| Ensemble | 612 452 | 612 532 | −80 ha (−0,01 %) | 3 339,7 / 3 339,8 | 962,6 / 962,9 |

- Les écarts de stock sont inférieurs ou égaux à 0,08 % par département (maximum : Val-de-Marne, −15 ha). Pour les flux, l'écart reste sous 0,2 % partout sauf dans deux petits départements : Paris (+2 % sur l'artificialisation, soit 0,09 ha/an) et Hauts-de-Seine (±1,2 %).
- Par commune, le 99ᵉ centile de l'écart de stock vaut 0,5 ha (0,5 %). Le maximum est à Paris (−3,8 ha) et à Fontenay-sous-Bois (−3,3 ha).
- Presque tous les désaccords portent sur des polygones IGN marqués `crit_seuil = True` : 141 ha sur 143 ha en 2021. Le recalcul classe un peu moins de surface en artificialisé que l'IGN (111 ha « IGN seul » contre 32 ha « recalcul seul »). La cause est l'approximation du seuillage, faite en un seul passage sans itération (voir `nomenclature.seuiller`).
- **Conclusion : le recalcul reproduit la couche officielle à la précision près du seuillage. Les écarts avec le MOS et les Fichiers fonciers ne viennent pas d'une erreur de recalcul.**

## 3. Part des retours qui relèvent de corrections du millésime 2021

Méthode : pour chaque polygone du patch, j'ai calculé le statut « brut » (règle du décret, avant seuillage) deux fois, avec les codes d'origine puis avec les codes corrigés. Cela donne trois types de patch :
- type 2 : le polygone passe de non artificialisé à artificialisé ;
- type 3 : il passe d'artificialisé à non artificialisé ;
- type 1 : son statut ne change pas.

Un **retour** (artificialisé en 2021, non artificialisé en 2024) situé sous un patch de type 3 est compté comme correction : avec le 2021 corrigé, il n'y aurait pas eu de retour. Symétriquement, une artificialisation sous un patch de type 2 est comptée comme correction. Le calcul est fait au pixel, sur la même grille que les flux.

| | retours (ha/an) | dont patch | artificialisation (ha/an) | dont patch | net publié → net hors corrections (ha/an) |
|---|---|---|---|---|---|
| IDF | 279,0 | 121,2 (**43 %**) | 1 185,7 | 330,7 (28 %) | 906,7 → 697,1 |
| HdF | 683,5 | 246,3 (**36 %**) | 2 154,0 | 585,5 (27 %) | 1 470,4 → 1 131,2 |
| Ensemble | 962,6 | 367,4 (**38 %**) | 3 339,7 | 916,2 (27 %) | 2 377,1 → 1 828,3 |

- Par département, la part des retours expliqués par le patch va de 19 % (Val-de-Marne) à 66–67 % (Paris, Hauts-de-Seine). Elle atteint 59 % dans le Val-d'Oise et 54 % dans les Yvelines.
- Les corrections touchent aussi les gains, souvent davantage en hectares. Le cas extrême est l'Aisne : 71 % de l'artificialisation brute (368 ha/an sur 518) relève du patch, et le net passe de 457 à 116 ha/an. Les principales corrections y sont des prairies agricoles (CS2.2.1 × US1.1) recodées en surfaces minérales agricoles (1 045 ha) ou en usage résidentiel (US3, 544 ha). Ce point est à vérifier avec l'IGN.
- Ce gonflement artificiel joue dans les deux sens. Le net « hors corrections » baisse dans 9 départements sur 13. Il monte dans 4 : Nord (+22 ha/an), Pas-de-Calais (+49), Hauts-de-Seine (+0,7) et, de façon marginale, Seine-Saint-Denis (+0,1). Dans ces départements, les corrections ont surtout produit de faux retours.
- La même méthode appliquée aux polygones du DIFF IGN donne des parts identiques : 38 % des désartificialisations et 27 % des artificialisations.

Typologie vectorielle complémentaire des 3 066 ha désartificialisés selon le DIFF IGN (13 départements, ha sur la période) :

| catégorie | surface | part |
|---|---|---|
| sous patch de type 3 | 1 179 ha | 38 % |
| hors patch, usage modifié (changement d'usage, a priori réel) | 1 041 ha | 34 % |
| hors patch, couverture modifiée sans changement d'usage (ambigu : renaturation réelle ou reclassement) | 787 ha | 26 % |
| hors patch, codes identiques (bascule due au seuillage ou au voisinage) | 58 ha | 2 % |

## Limites

- Le patch sert ici de « vérité » sur les erreurs 2021. Il ne couvre que les erreurs que l'IGN a corrigées, et rien n'est publié pour 2024 et 2025. La part de 38 % est donc plutôt un **minimum**. La catégorie « couverture modifiée sans changement d'usage » (26 %) peut contenir d'autres reclassements.
- L'effet du patch est évalué sur le statut avant seuillage, à la résolution de 5 à 15 m. Je n'ai pas relancé le seuillage sur un 2021 corrigé : les polygones redécoupés du patch (`decoup_geo = 1`) empêchent une substitution simple par identifiant.
- Je n'ai pas vérifié dans la documentation IGN ou ministérielle si la comptabilité ZAN officielle utilise le 2021 corrigé.
- Les exemptions (parcs, photovoltaïque) ne sont appliquées ni dans le recalcul ni dans la couche IGN utilisée (ressource `-EXEMPTIONS` non téléchargée).
- Le Nord est calculé sur 2021→2025 (4 ans) ; les autres départements sur 3 ans. Les totaux régionaux additionnent des rythmes en ha/an.
