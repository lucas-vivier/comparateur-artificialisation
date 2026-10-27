# Publier le comparateur : mode opératoire

Tout est prêt dans `~/Workspace/occupation-sol` : les 96 départements sont dans `web/`
(1 723 fichiers suivis, environ 450 Mo), la page `web/index.html` est testée.
Il reste à envoyer le dépôt sur GitHub : cela demande votre connexion GitHub, donc se fait
depuis votre Mac.

## Avant de lancer (2 décisions, 2 minutes)

1. **Licence du code** : `LICENSE` est en MIT au nom de Lucas Vivier. Si le code est un travail
   du groupe NAC, mettez les noms du groupe ou retirez le fichier.
2. **Police Marianne** : la page reprend la charte INSP (police Marianne, bleu État). L'usage de
   Marianne est réservé aux services de l'État (je ne l'ai pas vérifié en détail pour une
   production d'élèves INSP) : à confirmer, ou remplacer par une police neutre.

## Première publication (environ 15 minutes, une seule fois)

1. **Installer l'outil GitHub** si besoin, dans le Terminal :
   ```bash
   brew install gh
   ```
2. **Lancer le script** :
   ```bash
   cd ~/Workspace/occupation-sol
   bash publier.sh
   ```
   Le script :
   - vous connecte à GitHub (une page s'ouvre dans le navigateur : validez le code affiché) ;
   - range le workflow de publication dans `.github/workflows/` (je ne pouvais pas écrire dans
     ce dossier) ;
   - crée le dépôt git local, puis le dépôt public `lucas-vivier/comparateur-artificialisation` ;
   - envoie les fichiers (plusieurs minutes pour 450 Mo) ;
   - active GitHub Pages en mode « GitHub Actions » et lance la publication.
3. **Vérifier la publication** :
   ```bash
   gh run watch
   ```
   ou onglet **Actions** du dépôt. Si l'étape échoue avec une erreur Pages : dépôt >
   **Settings > Pages > Source : GitHub Actions**, puis **Actions > Publier le comparateur >
   Run workflow**.
4. **Ouvrir le site** : https://lucas-vivier.github.io/comparateur-artificialisation/
   Tester 94 (avec Parcelles), un département des Hauts-de-France et un département sans base
   régionale (35, par exemple).

## Ménage après publication (facultatif)

Deux dossiers de travail sont exclus du dépôt et peuvent être supprimés à la main :
- `_transfert/` : archives qui ont servi à rapatrier les 15 départements régionaux ;
- `_sauvegarde_web94_20261027/` : ancienne version du Val-de-Marne, remplacée par celle du
  comparateur publié (même version que sur claude.ai).

Le dossier `deploiement/` peut aussi être supprimé une fois le workflow copié dans `.github/`.

## Mettre à jour le site ensuite

Après avoir régénéré des fichiers dans `web/` :
```bash
cd ~/Workspace/occupation-sol
git add -A
git commit -m "Mise à jour du comparateur"
git push
```
La publication repart toute seule (2 à 5 minutes).

## Ce qui n'est pas publié

Données brutes et caches (`data/`), journaux (`logs/`), archives de calcul
(`outputs/france/*.zip`), correctifs de présentation (`outputs/france/deckpatch/`) et brouillons de
courriels aux producteurs (`outputs/pistes/E_brouillons_producteurs.md`). Voir `.gitignore`.
