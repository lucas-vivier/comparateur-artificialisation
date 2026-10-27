# Comparateur : priorité 1 (21/10/2026)

## Ce qui a changé
- **Seuillage recalé sur l'IGN.** L'écart venait de l'exclusion des taches au bord du département (tampon de 30 m), et non de l'absence d'itération. Sans cette exclusion, le Val-de-Marne passe de 17 ha à 0,4 ha d'écart en 2021 (comparaison polygone par polygone avec la couche ARTIFICIALISATION de l'IGN). Sur les 13 départements, le stock 2021 recalculé passe de −80 ha à −9 ha d'écart (612 523 ha recalculés contre 612 532 ha IGN). Le seuillage est aussi itératif désormais, mais cela ne change presque rien.
- **Nouvelle variante « 2021 corrigé ».** C'est la règle officielle appliquée à la carte 2021 après le patch correctif de l'IGN. La carte 2024 est inchangée. Méthode : on retire de la carte 2021 la surface couverte par le patch, puis on ajoute les polygones du patch avec leurs codes corrigés. La surface totale est conservée à 0,000 % près.
- **Nord : périodes alignées.** Les Fichiers fonciers passent sur 2021-2025, comme l'OCS GE et l'OCS2D. Une ligne « Période des rythmes » est affichée dans les tableaux.

## Résultats (ha et ha/an, règle officielle)
| dép. | stock 2021 | stock 2021 corrigé | brut artif. | brut artif. corrigé | désartif. | désartif. corrigé | net | net corrigé |
|---|---|---|---|---|---|---|---|---|
| 75 | 8784.0 | 8788.0 | 4.24 | 1.51 | 1.47 | 0.16 | 2.8 | 1.3 |
| 77 | 71306.0 | 71859.0 | 487.9 | 350.3 | 95.68 | 142.43 | 392.2 | 207.9 |
| 78 | 47969.0 | 48236.0 | 210.21 | 146.61 | 40.96 | 66.32 | 169.3 | 80.3 |
| 91 | 41491.0 | 41560.0 | 179.83 | 147.24 | 40.39 | 30.6 | 139.4 | 116.6 |
| 92 | 13791.0 | 13791.0 | 13.33 | 10.67 | 3.97 | 1.53 | 9.4 | 9.1 |
| 93 | 19732.0 | 19732.0 | 52.95 | 50.37 | 9.47 | 6.76 | 43.9 | 44.0 |
| 94 | 18333.0 | 18333.0 | 24.42 | 22.04 | 11.93 | 9.48 | 12.5 | 12.6 |
| 95 | 31158.0 | 31219.0 | 212.61 | 146.87 | 74.85 | 29.35 | 137.9 | 117.7 |
| 02 | 46967.0 | 49089.0 | 517.54 | 149.99 | 60.22 | 399.93 | 457.3 | -249.9 |
| 59 | 113516.0 | 113931.0 | 603.42 | 554.27 | 175.08 | 229.49 | 428.3 | 324.8 |
| 60 | 54918.0 | 55023.0 | 284.71 | 219.31 | 66.87 | 36.59 | 217.8 | 182.7 |
| 62 | 95651.0 | 95507.0 | 482.69 | 441.25 | 301.53 | 212.26 | 181.2 | 229.0 |
| 80 | 48907.0 | 49045.0 | 265.28 | 214.37 | 79.85 | 74.81 | 185.4 | 139.6 |
| **Total** | 612523.0 | 616113.0 | 3339.1 | 2454.8 | 962.3 | 1239.7 | 2377.4 | 1215.7 |

Source : web/<dép>/data.json (calcul NAC sur grille de 5 à 15 m), outputs/prio1/bilan.txt.

## Lecture
- Avec la carte 2021 corrigée, le rythme net est divisé par deux environ : de 907 à 590 ha/an en Île-de-France, de 1 470 à 626 ha/an dans les Hauts-de-France. Le patch ajoute surtout des surfaces artificialisées dès 2021 (stock 2021 : +3 590 ha). Des « gains » 2021-2024 disparaissent donc, car ces surfaces étaient déjà artificialisées (gains bruts : 3 339 à 2 455 ha/an). En revanche, les retours augmentent (962 à 1 240 ha/an), là où la carte 2024 ne reprend pas la correction faite en 2021.
- Les effets ne vont pas tous dans le même sens : le net baisse dans 10 départements et monte dans le Pas-de-Calais (181 à 229 ha/an). Il ne bouge presque pas dans les Hauts-de-Seine, la Seine-Saint-Denis et le Val-de-Marne.
- **Aisne [à vérifier avec l'IGN]** : le patch reclasse environ 1 045 ha de prairies agricoles (CS2.2.1 × US1.1) en surfaces minérales (CS1.1.2.1 × US1.1), et 900 ha en usage résidentiel. Sur la moitié de ces surfaces, la carte 2024 garde le classement d'origine (prairie, US1.1). D'où un net corrigé négatif (−250 ha/an). Il s'agit d'une incohérence entre le patch 2021 et le millésime 2024, ou d'une lecture du patch à confirmer : ce n'est pas un chiffre à utiliser tel quel.
- Seine-et-Marne et Yvelines : le net corrigé baisse fortement (392 à 208, 169 à 80 ha/an).

## Limites
- On ne sait pas encore si le décompte officiel du ZAN utilisera le 2021 corrigé (question posée à l'IGN).
- Aucun patch n'existe pour 2024 et 2025.
- Les exemptions (parcs, photovoltaïque) ne sont pas appliquées.

Code : src/occsol/nomenclature.py (seuiller), scripts/corriger_2021.py, scripts/pipeline_dep.py (variante « corrige », classement sans exclusion du bord).
