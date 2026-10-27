# Piste B : Fichiers fonciers (Cerema CONSOENAF) face à l'OCS GE et au MOS / OCS2D

*Compte rendu de travail du 21/10/2026. Les chiffres viennent des scripts listés en fin de page. Tous les flux sont **bruts**, en ha/an, sauf mention contraire.*

## 1. Alignement des périodes et destinations (fichier communal)

Source : `data/raw/cerema/conso_com_2011_2025.csv`, en m². `nafAAartBB` est le flux entre le 1er janvier 20AA et le 1er janvier 20BB.

- Période **2021-2024** : 3 pas annuels (21→22, 22→23, 23→24). On la compare à l'OCS GE 2021→2024 et à l'OCS2D HdF 2021→2024 (02, 60, 62, 80).
- Période **2021-2025** : 4 pas annuels. On la compare au MOS IDF 2021→2025 et au Nord (OCS GE et OCS2D 2021→2025).
- Limite (non vérifié) : les millésimes OCS GE et MOS sont datés par la prise de vue, pas au 1er janvier. L'alignement est donc approché, à quelques mois près.
- Pour chaque département, la somme des six destinations est égale au total (écart nul).

**Destinations, période 2021-2024** (`piste_B_destinations_departements.csv`) :

- L'habitat représente 33 à 65 % du flux et l'activité 22 à 52 %. Le 93 fait exception, avec 84 % d'activité.
- Les routes pèsent de 3 à 8 % (0 % à Paris et dans le 92).
- Le ferré est presque nul partout, sauf dans le 94 : 1,96 ha, soit 11 % d'un flux très faible.
- La part de l'**inconnu** va de 0 % (92, 94) à 10 % (95, 02). Sur 2021-2025, elle atteint 13,9 % dans le 93.
- Paris (75) : flux FF nul sur les deux périodes.

**Rapport FF / OCS GE à période égale** (`piste_B_comparaison_periodes.csv`) :

- Il va de 0,05 (92) et 0,25 (94, 02) à 0,77 (91, 62). Il vaut 0,58 dans le Nord sur 2021-2025.

**Rapport FF / MOS-OCS2D** :

- Il est proche de 1 dans le 77 (0,96), le 02 (1,00) et le 60 (0,97).
- Il est de 0,63 à 0,80 dans les 78, 95, 59, 62 et 80.
- Il dépasse 1 dans le 91 (1,39) et le 93 (1,52).

## 2. Comparaison spatiale au carreau 1 km (94 et 59)

**Données.** Le carroyage vient du jeu data.gouv.fr « Consommation d'espaces naturels, agricoles et forestiers du 1er janvier 2011 au 1er janvier 2025 » (Cerema). URL relevée via l'API data.gouv.fr :

https://static.data.gouv.fr/resources/consommation-despaces-naturels-agricoles-et-forestiers-du-1er-janvier-2011-au-1er-janvier-2025/20260511-111136/conso-carroyage.gpkg

Le fichier pèse 95 Mo. Il contient 255 233 carreaux en EPSG:3035, avec les valeurs en ha (dictionnaire Cerema). Il est stocké dans `data/raw/cerema/carroyage/`.

**Méthode.**
- Le statut OCS GE « reference » est rastérisé par lots de 100 000 polygones : grille de 5 m pour le 94, de 15 m pour le 59, comme dans `pipeline_dep.py`.
- Chaque pixel devenu artificialisé est rattaché au carreau qui contient son centre.
- Le FF est lu par bbox, sur la même période : 2021-2024 pour le 94, 2021-2025 pour le 59.
- Les statistiques portent sur les carreaux inclus à au moins 99 % dans le département.
- Contrôle : les totaux OCS GE recalculés égalent ceux de `data.json` (24,51 et 603,61 ha/an).

| | 94 (194 carreaux) | 59 (5 351 carreaux) |
|---|---|---|
| Flux OCS GE / FF sur la période (ha) | 64,0 / 16,3 | 2 312 / 1 338 |
| Pearson / Spearman | 0,24 / 0,29 | 0,31 / 0,35 |
| Pearson sur log(1+x) | 0,28 | 0,39 |
| Carreaux avec OCS > 0 et FF = 0 | 93 | 1 198 |
| Carreaux avec FF > 0 et OCS = 0 | 7 | 638 |
| Top 10 % des carreaux communs aux deux sources | 5 sur 19 | 184 sur 534 |
| Corrélation routes OCS (US4.1.1) / FF « rou » | 0,10 | 0,03 |

Les deux sources se recoupent peu au carreau.
- Le FF est très concentré dans le 94 : 95 % du flux tient dans 10 % des carreaux, contre 58 % pour l'OCS GE.
- Dans le 59, les totaux « routes » se ressemblent (71 ha pour l'OCS, 64 ha pour le FF), mais ils ne tombent pas dans les mêmes carreaux.
- Selon le Cerema, le carroyage n'est **pas exhaustif** : les flux non géolocalisés n'y figurent pas. Ses totaux ne valent donc que pour un ordre de grandeur.

## 3. Ce que les FF ne voient pas : infrastructures et domaine non cadastré

### Méthode Cerema

Sources : guide CONSOENAF du Cerema, https://doc-datafoncier.cerema.fr/doc/guide/conso-enaf, pages « Définition de la consommation d'espace », « Guide complet » et « Données à l'échelle carroyée », consultées le 21/10/2026.

- La consommation est le flux **NAF → urbanisé cadastré**, calculé à l'îlot de parcelles.
- Les flux entre NAF, urbanisé et **non cadastré** sont calculés à part.
- La destination « route » ou « fer » est attribuée après coup aux parcelles consommées que la BD TOPO recouvre : plus de 45 % de la parcelle pour la route, plus de 30 % pour le fer. Les tampons utilisés sont la largeur de chaussée + 4 m, 30 m pour une LGV, et 6 m par voie pour les autres lignes.
- Les chemins ruraux et les bâtiments agricoles hors serres ne sont pas comptés.

Inférence (non vérifiée dans les tables Cerema) : une emprise NAF qui passe directement dans le domaine public non cadastré, comme une nouvelle voirie, n'entre pas dans `naf..art..`.

### Ordre de grandeur (`piste_B_infrastructures_ecart.csv`, 13 départements)

On a recalculé les flux OCS GE en notant l'usage US au second millésime.

**Infrastructures.**
- Les usages US4.1.x (routes, fer, autres transports) représentent 165 ha/an sur 3 340, soit **≈ 5 %** de l'OCS GE devenu artificialisé.
- Selon les départements, leur part va de 3 % (78, 02, 59) à 12 % (91, 95).
- Les routes et le fer des FF totalisent 102 ha/an.
- Le surplus « infrastructures » de l'OCS GE n'est donc que de **≈ 62 ha/an**, soit environ 4 % de l'écart total OCS GE − FF (1 476 ha/an).
- Il est plus marqué dans le 91 (12 ha/an, 29 % de l'écart, ferré surtout), le 95 (20 ha/an, 14 %, dont les US4.1.3-5) et le 75 (9 %).

**Autres usages, plus lourds.** Leur poids dans l'écart est une piste, pas une mesure (non vérifié).
- **US6.1 « zones en transition »** (chantiers) : 631 ha/an. Hypothèse : le cadastre enregistre ces surfaces avec retard, au fil des déclarations, alors que le guide parle d'un délai pouvant aller jusqu'à 5 ans pour un aménagement.
- **US1.1 « agriculture »** : 375 ha/an. Les bâtiments agricoles ne sont pas dans les FF, selon le Cerema.

## Limites

- Le rattachement au carreau se fait par le centre de pixel, sur une grille de 15 m pour le 59 : approximation de bordure.
- Les flux FF sont des flux d'îlots sur une base fiscale, alors que l'OCS GE mesure un changement de statut physique. Les deux sources ne mesurent pas le même objet.
- Les flux OCS GE ne sont pas filtrés sur l'état NAF d'origine : ils comptent tout passage de non artificialisé à artificialisé.
- Le retour en non artificialisé n'est pas comparé : selon le Cerema, le flux FF urbanisé → NAF n'est pas fiable.
- Le processus du 02 a atteint 2,6 Go de mémoire, au-dessus de la cible de 2,5 Go.

## Fichiers

- Scripts : `scripts/piste_B_destinations.py`, `scripts/piste_B_carroyage.py <dep>` (lancé sous `flock .heavy.lock`), `scripts/piste_B_synthese_infra.py`.
- Tables (`outputs/tables/`) :
  - `piste_B_destinations_departements.csv`
  - `piste_B_comparaison_periodes.csv`
  - `piste_B_carreaux_{94,59}.csv`
  - `piste_B_correlation_{94,59}.csv`
  - `piste_B_usages_flux_<dep>.csv`, pour les 13 départements
  - `piste_B_infrastructures_ecart.csv`
