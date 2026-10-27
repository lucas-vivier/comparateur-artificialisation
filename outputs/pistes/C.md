# Piste C — Décomposition des écarts entre base régionale et OCS GE (stock 2021)

*21/10/2026. Scripts : `scripts/piste_C_ecarts.py` (un département, sous `flock`), `scripts/piste_C_synthese.py` (léger).
Tables : `outputs/tables/piste_C_*.csv` ; détail brut par département dans `outputs/tables/piste_C/<dep>_{matrice,familles,variantes}.csv`.*

## 1. Méthode

- **Grille.** C'est la grille de `pipeline_dep.py` en Lambert-93 : pas de 5 m (75, 91 à 95), 10 m (78) ou 15 m (77 et HdF). L'ordre de rastérisation est le même. J'ai rastérisé **l'indice du polygone** pour l'OCS GE 2021 et pour la base régionale 2021 : MOS IDF à 79 postes, ou OCS2D HdF (couche `ocs2d_enaf_opendata`, avec les champs `enaf_2021`, `urba_2021`, `cs21` et `us21`). Les pixels sont ensuite comptés par couple de polygones. Chaque couple porte les attributs suivants : CS, US, statut brut, statut final pour les 5 variantes, bascule au seuillage, et poste ou classe régionale.
- **Contrôle.** L'accord pixel « reference » retrouve `data.json` (`departement.mos.accord_2021`) **à l'identique dans les 13 départements** (écart 0,0000). Il en va de même pour `ocs_seul_ha` et `mos_seul_ha`.
- **Sens des désaccords.** D1 = OCS GE artificialisé / base régionale ENAF (NAF). D2 = OCS GE non artificialisé / base régionale urbaine (non-NAF).
- **Familles.** Chaque pixel est rangé dans la première famille qui s'applique, dans l'ordre ci-dessous.
  - D1 : (b) seuil ou généralisation → (a) herbacé CS2.2 artificialisé par son usage → (c) US1.3, US4.x, US6.1 → (d) bâti CS1.1.1.1 ou usage US5/US235 → (e) résidu.
  - D2 : (b) → (c) chantiers, carrières, infrastructures. Côté MOS : postes 46-54 et 73-79. Côté OCS2D : classe `Infrastructure` ou `us21` en US6.1/US1.3. Côté OCS GE : mêmes usages qu'en D1. → (a) espaces verts urbains. MOS : postes 13-15 et 17-27. OCS2D : classes `Activité` ou `Urbanisé autre` sur végétation OCS GE CS2.x. → (d) jardins et habitat individuel. MOS : postes 16 et 28-30. OCS2D : `Habitat`. → (e).
  - **(b) regroupe deux cas.** Le premier est la bascule au seuillage de 2 500 m² (statut brut ≠ statut final). Le second est un « contour » : une intersection de moins de 0,25 ha et de moins de 25 % de chacun des deux polygones, ce qui signale un décalage de limites ou une généralisation. Ces deux seuils sont des choix de ma part, pas une norme.

## 2. Résultats : surfaces en désaccord (ha) et part de chaque famille

| | D1 OCS artif / régional ENAF | dont a | b | c | d | e | D2 OCS non artif / régional urbain | dont a | b | c | d | e |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IDF | 11 063 | 63 % | 22 % | 5 % | 5 % | 5 % | 52 611 | 43 % | 11 % | 15 % | 25 % | 6 % |
| HdF | 29 130 | 58 % | 15 % | 3 % | 12 % | 11 % | 75 555 | 31 % | 15 % | 24 % | 28 % | 2 % |
| Ensemble | 40 193 | 60 % | 17 % | 4 % | 10 % | 9 % | 128 166 | 36 % | 13 % | 20 % | 27 % | 4 % |

Le détail par département est dans `piste_C_familles.csv`.

- **Les désaccords sont asymétriques.** D2 est 3,2 fois plus étendu que D1. Au total, le stock OCS GE reste inférieur à la base régionale de 41 547 ha en IDF et de 46 425 ha en HdF.
- **D2 relève surtout de la végétation en tissu urbain.** 76 100 ha sur 128 200 sont des ligneux (CS2.1 : 35 566 ha en IDF, 40 556 ha en HdF). La règle du décret ne les artificialise jamais. Les herbacés CS2.2 que leur usage ne rend pas artificialisés (surtout US1.1 et US6.3) comptent pour 46 700 ha. En IDF, les postes MOS les plus touchés sont les jardins de l'habitat (16 : 9 362 ha), les parcs et jardins publics (13 : 5 604 ha) et les autres espaces verts (14 : 2 699 ha). La règle OCS GE et la base régionale divergent donc sur le principe même de ce qu'elles comptent (couverture contre usage). Ce n'est pas une erreur de l'une ou de l'autre.
- **D1 vient d'abord de la catégorie 5, l'herbacé artificialisé par son usage** (60 %). Les usages en cause sont surtout résidentiel US5 et tertiaire US3. La base régionale range ces surfaces en agricole, naturel ou forêt : par exemple 7 385 ha de CS2.2.1 × US5 classés « Agricole » en HdF. Les usages de transport et de réseaux (US4) n'en représentent que 1 057 ha en IDF et 986 ha en HdF.
- **Le seuil de 2 500 m² pèse peu en lui-même.** La bascule au seuillage ne représente que 1 072 ha sur l'ensemble des deux sens. L'essentiel de la famille (b) est fait de contours : 22 811 ha, soit 95 % de (b).
- **Le résidu D1 en HdF est surtout agricole anthropisé** (CS1.1.2.1 × US1.1 : 1 796 ha). Il s'agit probablement de cours de ferme ou de chemins, mais je ne l'ai pas vérifié.
- **Écarts entre départements.** La famille (a) domine D2 en petite couronne et à Paris (44 à 68 %). La famille (d), jardins et habitat individuel, pèse davantage en grande couronne et en HdF (21 à 34 %).

## 3. Effet des variantes de règle sur l'accord avec la base régionale

Accord au pixel (stock 2021). Source : `piste_C_variantes_accord.csv`. Les flux viennent de `data.json`.

| | reference | sans_herbace | seuil_0 | seuil_1000 | seuil_5000 |
|---|---|---|---|---|---|
| IDF | 94,72 % | 88,71 % | 94,28 % | 94,42 % | **94,97 %** |
| HdF | 96,73 % | 93,21 % | 96,61 % | 96,65 % | **96,78 %** |
| Ensemble | 96,18 % | 91,98 % | 95,98 % | 96,04 % | **96,29 %** |

- **Exclure l'herbacé (`sans_herbace`) dégrade fortement l'accord.** L'écart de stock passe de −88 000 ha à −330 600 ha. Le recul atteint −12 à −13 points dans les Hauts-de-Seine, la Seine-Saint-Denis et le Val-de-Marne. Côté flux, le net OCS GE de l'ensemble devient proche du net régional (1 610 contre 1 621 ha/an). Ce rapprochement est fortuit : le brut, lui, reste à 3 178 contre 2 206 ha/an.
- **Relever le seuil à 5 000 m² améliore légèrement l'accord** (+0,1 point sur l'ensemble, +1,1 à +1,5 point en petite couronne et à Paris). Le supprimer (`seuil_0`) le dégrade. Aucune variante de seuil ne change l'ordre de grandeur des écarts de flux : le brut OCS GE vaut environ 1,5 fois la consommation brute régionale.

## 4. Limites

- L'analyse porte sur le stock 2021 seulement. Je n'ai pas décomposé les flux 2021→2024/2025 par famille.
- **Résolution.** Au pas de 15 m (77 et HdF), les objets étroits sont dégradés. Cela concerne surtout la famille (b), qui est donc sensible au pas de grille.
- **Codes OCS2D.** Hors classes `enaf`, je les ai lus par analogie avec l'OCS GE (US6.1 = transition, US1.3 = extraction). Cette lecture est **non vérifiée** : je n'ai pas trouvé la nomenclature OCS2D en ligne pendant ce travail.
- **Classement en familles.** Il repose sur des règles de priorité et des seuils de « contour » que j'ai choisis. Une autre priorité, par exemple (c) avant (a) pour l'herbacé des bords de route, déplacerait environ 2 000 ha de D1. Le résidu (e) reste faible, entre 4 et 9 %.
- **Mémoire.** La cible était de 2,5 Go par processus. Le pic mesuré va de 0,6 à 2,9 Go selon le département : 2,6 à 2,9 Go pour le 77, le 91, le 95, le 59 et le 62. La Somme, l'Oise et l'Aisne ont tourné avec la première version, qui lisait l'OCS2D par morceaux de 300 000 ; leur pic a atteint 3,5, 3,1 et 3,7 Go. Je suis ensuite passé à des morceaux de 100 000. Aucun OOM ne s'est produit.
