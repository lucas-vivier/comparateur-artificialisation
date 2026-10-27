# Piste D : synthèse pour la note de validation du comparateur

*21/10/2026. Ce texte reprend les comptes rendus `outputs/pistes/A.md`, `B.md`, `C.md` et `E_brouillons_producteurs.md`, ainsi que les tables `outputs/tables/piste_*.csv`. Il n'y a aucun nouveau calcul, à deux exceptions près : les sommes régionales des tables B et C, faites à partir des colonnes indiquées. Le comparateur (`pipeline_dep.py`, `web/`) n'a pas été modifié.*

*Convention : les flux sont en ha/an. La période est 2021→2024 pour l'OCS GE et l'OCS2D, sauf pour le Nord (59) : 2021→2025 en OCS GE comme en OCS2D. Elle est 2021→2025 pour le MOS. Les totaux « ensemble » et « HdF » additionnent donc des rythmes calculés sur 3 et 4 ans. Les mentions **[incertain]** signalent un chiffre fragile.*

---

## 1. Ce que l'outil reproduit des chiffres officiels

**Comparaison avec la couche officielle IGN (OCSGE-ARTIFICIALISATION).** Source : `piste_A_validation_ign.csv`, lignes IDF, HdF et ensemble.

| | Stock 2021 recalculé / IGN (ha) | Écart | Artificialisation recalc. / IGN | Désartificialisation recalc. / IGN |
|---|---|---|---|---|
| IDF | 252 500 / 252 568 | −68 ha (−0,03 %) | 1 185,7 / 1 185,6 | 279,0 / 279,1 |
| HdF | 359 952 / 359 964 | −12 ha (−0,003 %) | 2 154,0 / 2 154,2 | 683,5 / 683,8 |
| Ensemble | 612 452 / 612 532 | −80 ha (−0,01 %) | 3 339,7 / 3 339,8 | 962,6 / 962,9 |

**Par département.**
- L'écart de stock ne dépasse pas 0,08 %. Le maximum est dans le Val-de-Marne (−15 ha).
- L'écart sur les flux reste sous 0,2 %, avec deux exceptions : Paris (+2 %, soit +0,09 ha/an) et les Hauts-de-Seine (±1,2 %). Source : même table.

**Par commune (5 048).** 99 % des écarts de stock sont inférieurs ou égaux à 0,5 ha. Le maximum est à Paris (−3,8 ha). Source : `piste_A_validation_ign_communes.csv`.

**Origine des désaccords.** Presque tous portent sur des polygones touchés par le seuillage des 2 500 m² (`crit_seuil`) : 141 ha sur 143. Notre code fait ce seuillage en un seul passage, sans itérer, d'où l'écart (voir `A.md` §2).

**Contrôles de cohérence internes.**
- Les accords « reference » au pixel avec le MOS et l'OCS2D retrouvent `data.json` à l'identique dans les 13 départements (`C.md` §1).
- Les flux OCS GE recalculés au carreau retrouvent `data.json` : 24,51 ha/an dans le 94 et 603,61 ha/an dans le 59 (`B.md` §2).

**Conclusion.** Le comparateur reproduit la couche officielle, à la précision du seuillage près. Les écarts avec le MOS, l'OCS2D et les Fichiers fonciers ne viennent donc pas d'une erreur de recalcul.

**Constat sur les couches officielles.** La couche ARTIFICIALISATION 2021 et le différentiel `zan_evol` portent les codes 2021 **non corrigés** par le patch IGN. Les flux officiels incluent donc l'effet des corrections du millésime 2021. Ce constat a été vérifié en détail sur Paris et par égalité DIFF = différence des millésimes sur les 13 départements (`A.md` §1).

## 2. Décomposition des écarts

### 2.1 Les flux OCS GE contiennent des corrections de millésime

Source : `piste_A_validation_ign.csv`, colonnes `*_patch_*`.

| | Retours dus au patch | Gains dus au patch | Net publié → net hors corrections |
|---|---|---|---|
| IDF | 121,2 / 279,0 (43 %) | 330,7 / 1 185,7 (28 %) | 906,7 → 697,1 |
| HdF | 246,3 / 683,5 (36 %) | 585,5 / 2 154,0 (27 %) | 1 470,4 → 1 131,2 |
| Ensemble | 367,4 / 962,6 (38 %) | 916,2 / 3 339,7 (27 %) | 2 377,1 → 1 828,3 |

- **Retours.** La part due au patch va de 19 % dans le Val-de-Marne à 66–67 % à Paris et dans les Hauts-de-Seine.
- **Le net hors corrections** baisse dans 9 départements. Il monte dans 4 : Nord (+22), Pas-de-Calais (+49), Hauts-de-Seine (+0,7) et Seine-Saint-Denis (+0,1).
- **Aisne [incertain, à vérifier avec l'IGN].** 71 % des gains (368 ha/an sur 518) relèvent du patch, et le net passe de 457 à 116 ha/an.
- **Désartificialisations du DIFF IGN, par cause** (3 066 ha sur la période) :
  - corrections : 38 % ;
  - changements d'usage : 34 % ;
  - changements de couverture sans changement d'usage : 26 %, cause ambiguë ;
  - effets du seuillage : 2 %.
- **[incertain]** Ces 38 % sont un minimum, car le patch ne couvre que les erreurs 2021 que l'IGN a corrigées. L'effet du patch est en outre mesuré avant le seuillage.

### 2.2 OCS GE / MOS-OCS2D : le stock 2021 par famille

Source : `piste_C_familles.csv`.

- **D1** : l'OCS GE dit artificialisé, la base régionale dit ENAF.
- **D2** : l'OCS GE dit non artificialisé, la base régionale dit urbain.

| Famille | D1 IDF | D1 HdF | D1 ensemble | D2 IDF | D2 HdF | D2 ensemble |
|---|---|---|---|---|---|---|
| Total (ha) | 11 063 | 29 130 | 40 193 | 52 611 | 75 555 | 128 166 |
| (a) herbacé artificialisé / espaces verts urbains | 63 % | 58 % | 60 % | 43 % | 31 % | 36 % |
| (b) seuil 2 500 m² et généralisation | 22 % | 15 % | 17 % | 11 % | 15 % | 13 % |
| (c) chantiers, carrières, infrastructures | 5 % | 3 % | 4 % | 15 % | 24 % | 20 % |
| (d) jardins et bâti diffus | 5 % | 12 % | 10 % | 25 % | 28 % | 27 % |
| (e) résidu | 5 % | 11 % | 9 % | 6 % | 2 % | 4 % |

- **Bilan de stock.** L'OCS GE est plus bas que la base régionale : −41 547 ha en IDF et −46 425 ha en HdF (`piste_C_variantes_accord.csv`, colonne `ecart_stock_ha`, variante reference).
- **D2 est surtout de la végétation en ville.** Les ligneux (CS2.1) en font 76 100 ha sur 128 200 ; la règle du décret ne les artificialise jamais. En IDF, les postes MOS les plus touchés sont le 16 (jardins de l'habitat, 9 362 ha) et le 13 (parcs et jardins publics, 5 604 ha) (`piste_C_matrice_postes_mos_idf.csv`). C'est une **divergence de définition** (couverture contre usage), pas une erreur de l'une ou l'autre base.
- **D1 vient surtout de l'herbacé artificialisé par son usage.** Exemple : 7 385 ha d'herbacé CS2.2.1 à usage résidentiel US5 classés « Agricole » en HdF (`C.md` §2).
- **Le seuil de 2 500 m² pèse peu en lui-même** : 1 072 ha. Plus de 95 % de la famille (b) vient de décalages de contours (`piste_C_detail_seuil.csv`).
- **Selon les territoires.** (a) domine D2 à Paris et en petite couronne (44 à 68 %). (d) pèse 21 à 34 % en grande couronne et en HdF.
- **Variantes de règle** (accord au pixel sur l'ensemble, `piste_C_variantes_accord.csv`) :
  - reference 96,18 % ; sans_herbace 91,98 % ; seuil_0 95,98 % ; seuil_1000 96,04 % ; seuil_5000 96,29 %.
  - Le rapport des flux bruts OCS GE / régional reste d'environ 1,5 quelle que soit la variante. Il vaut 1,71 en IDF et 1,42 en HdF en variante reference (même table, colonne `ratio_flux_brut`).
- **Flux bruts** : OCS GE 3 339,7 ha/an contre 2 206,4 ha/an pour le MOS et l'OCS2D (somme de `piste_B_comparaison_periodes.csv`). Par région : IDF 1 185,7 contre 693,2 ; HdF 2 154,0 contre 1 513,2.
- **Non décomposé.** Les flux 2021→2024/2025 n'ont pas été découpés par famille.

### 2.3 OCS GE et MOS-OCS2D face aux Fichiers fonciers

Sources : `piste_B_comparaison_periodes.csv`, `piste_B_destinations_departements.csv`, `piste_B_infrastructures_ecart.csv`, `piste_B_correlation_{94,59}.csv`.

**Flux FF à période égale.**
- Face à l'OCS GE, le FF totalise 1 863,6 ha/an, contre 3 339,7 pour l'OCS GE. Par région : IDF 656,7 contre 1 185,7 ; HdF 1 206,9 contre 2 154,0. L'écart total est de 1 476 ha/an.
- Face au MOS et à l'OCS2D, il totalise 1 850,5 ha/an, contre 2 206,4.

**Rapports par département.**
- FF / OCS GE : de 0,05 (92) à 0,77 (91, 62) ; 0,58 dans le Nord. Paris a un flux FF nul.
- FF / MOS-OCS2D : environ 1 dans le 77, le 02 et le 60 ; 0,63 à 0,80 dans le 78, le 95, le 59, le 62 et le 80 ; 1,39 dans le 91 et 1,52 dans le 93.
- **[incertain]** Le 92 donne 4,27, mais sur des flux minimes (0,33 contre 1,41 ha/an).

**Destinations FF 2021-2024.**
- Habitat : 33 à 65 %. Activité : 22 à 52 %, et 84 % dans le 93. Routes : 3 à 8 %.
- Part « inconnu » : de 0 à 10 %, et 13,9 % dans le 93 sur 2021-2025.

**Infrastructures.**
- Les usages US4.1.x pèsent 165 ha/an, soit environ 5 % du flux OCS GE.
- Après retrait des routes et du fer comptés par les FF (102 ha/an), il reste environ 62 ha/an, soit environ 4 % de l'écart OCS GE − FF.
- Cette part est plus forte dans le 91 (29 %), le 95 (14 %) et le 75 (9 %).

**Usages plus lourds, non attribués à l'écart.** **[incertain : piste, pas une mesure]**
- US6.1, zones en transition (chantiers) : 631 ha/an.
- US1.1, agriculture : 375 ha/an. Selon le guide Cerema, les bâtiments agricoles ne sont pas comptés dans les FF.

**Comparaison au carreau de 1 km.** Les deux sources se recoupent peu.
- Pearson et Spearman : 0,24 et 0,29 dans le 94 ; 0,31 et 0,35 dans le 59.
- Carreaux du top 10 % communs aux deux sources : 5 sur 19 dans le 94, 184 sur 534 dans le 59.
- Corrélation des routes : 0,10 dans le 94 et 0,03 dans le 59.
- Le carroyage Cerema ne contient pas les flux non géolocalisés. Il ne donne donc qu'un ordre de grandeur.

## 3. Limites et incertitudes

1. **Seuillage.** Il est approché en un seul passage. C'est la seule source mesurable d'écart avec l'IGN (A).
2. **Corrections IGN.**
   - Il n'existe ni patch ni millésime corrigé pour 2024/2025.
   - Je n'ai pas vérifié si la comptabilité ZAN officielle utilise le 2021 corrigé (A).
   - Les exemptions (parcs, photovoltaïque) ne sont appliquées ni dans le recalcul ni dans la couche IGN utilisée (A).
3. **Périodes hétérogènes.**
   - Le Nord est calculé sur 4 ans, les autres départements sur 3, et les totaux régionaux additionnent ces rythmes.
   - **[non vérifié]** L'alignement des dates de prise de vue OCS GE/MOS sur le 1er janvier, date de référence des FF (B).
4. **Objets mesurés différents.**
   - Les FF reposent sur une base fiscale par îlots ; l'OCS GE sur un statut physique. Les flux OCS GE ne sont pas filtrés sur l'état NAF d'origine (B).
   - **[inférence non vérifiée]** Une voirie passée directement en domaine public non cadastré échapperait aux FF (B).
5. **Familles C.**
   - L'ordre de priorité et les seuils de « contour » (moins de 0,25 ha et moins de 25 % de chaque polygone) sont des choix d'analyse. Classer l'herbacé des bords de route en (c) plutôt qu'en (a) déplacerait environ 2 000 ha de D1.
   - **[non vérifié]** Les codes OCS2D hors classes `enaf` ont été lus par analogie avec l'OCS GE.
   - **[incertain]** La grille de 15 m (77 et HdF) rend la famille (b) sensible au pas.
6. **Règle MOS : postes 1 à 12 = ENAF.** C'est un choix du projet, non validé par l'Institut Paris Region. Les postes 10 (serres) et 11–12 (eau) restent discutables (E).
7. **Exécution.** Des pics de mémoire ont dépassé la cible de 2,5 Go : jusqu'à 3,7 Go pour l'Aisne en piste C, et 2,6 Go pour l'Aisne en piste B. Il n'y a pas eu d'OOM, et cela n'a pas d'effet sur les chiffres.

## 4. Questions ouvertes aux producteurs

Les brouillons sont dans `outputs/pistes/E_brouillons_producteurs.md`. Rien n'a été envoyé. Il reste à compléter la signature et à vérifier les noms de champs OCS2D avant tout envoi.

- **IGN (OCS GE)** :
  - Existe-t-il des millésimes corrigés, et comment identifier la version d'un lot téléchargé ?
  - Quelle est la part des corrections dans le DIFF ? Le cas de l'Aisne est à soumettre.
  - Quel est le calendrier pour les 13 départements ?
  - Le contact `ocsge-bc@ign.fr` est peut-être inadapté à la question du calendrier.
- **Institut Paris Region (MOS)** :
  - Confirmer que les postes 1 à 12 sont des ENAF, notamment les postes 10 à 14.
  - Méthode de passage 2021→2025.
  - Existe-t-il une table de passage MOS↔OCS GE ?
- **Cerema (FF)** :
  - Traitement du domaine public non cadastré.
  - Destination « inconnu ».
  - Méthode du carroyage.
  - Éditions antérieures.
- **Géo2France (OCS2D)** :
  - Comment `enaf_2021` et `urba_2021-2024` sont-ils dérivés ?
  - Correspondance avec la nomenclature OCS GE.
  - Ce qui distingue la version v2.

## 5. Prochaines étapes

1. **Seuillage.** Rendre le seuillage itératif, pour fermer les 143 ha d'écart avec l'IGN, puis relancer la comparaison A.
2. **Variante « 2021 corrigé ».** Ajouter au comparateur une variante sur un 2021 corrigé par le patch, en refaisant le seuillage. Cela suppose de traiter les polygones redécoupés (`decoup_geo = 1`). Faire valider le résultat par l'IGN, en commençant par l'Aisne.
3. **Flux par famille.** Décomposer les flux 2021→2024/2025 par famille, comme pour le stock en C. Mesurer en priorité la part de l'US6.1 (chantiers) et de l'US1.1 dans l'écart OCS GE − FF.
4. **Nomenclature OCS2D.** L'obtenir et vérifier la lecture des codes. Vérifier aussi les champs de `ocs2d_enaf_2024_v2.gpkg`.
5. **Carroyage.** Étendre la comparaison au carreau aux 11 autres départements ; les tables existent déjà mais ne sont pas commentées.
6. **Exemptions.** Télécharger la ressource IGN `-EXEMPTIONS` et mesurer son effet.
7. **Producteurs.** Envoyer les demandes E après relecture humaine, puis intégrer les réponses à la note.
8. **Affichage.** Dans la note et dans l'interface, afficher les rythmes du Nord séparément, ou les ramener sur 3 ans.
