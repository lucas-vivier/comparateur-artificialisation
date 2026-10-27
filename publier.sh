#!/usr/bin/env bash
# Première publication du dépôt occupation-sol sur GitHub + activation de GitHub Pages.
# À lancer UNE fois, depuis un Terminal du Mac :  bash publier.sh
# Pour les mises à jour suivantes : git add -A && git commit -m "…" && git push
set -euo pipefail
cd "$(dirname "$0")"

DEPOT="lucas-vivier/comparateur-artificialisation"

if ! command -v gh >/dev/null 2>&1; then
  echo "L'outil GitHub (gh) n'est pas installé. Installez-le avec :  brew install gh"
  echo "puis relancez :  bash publier.sh"
  exit 1
fi

# 1. Connexion à GitHub (ouvre le navigateur la première fois)
gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git

# 2. Identité git (utilisée pour signer les commits)
git config --global user.name  >/dev/null || git config --global user.name  "Lucas Vivier"
git config --global user.email >/dev/null || git config --global user.email "79191733+lucas-vivier@users.noreply.github.com"

# 3. Dépôt local
if [ ! -d .git ]; then
  git init -b main
fi
git add -A
echo "Fichiers suivis : $(git ls-files | wc -l | tr -d ' ')   (taille du dossier web : $(du -sh web | cut -f1))"
git diff --cached --quiet || git commit -m "Comparateur d'occupation du sol : code et site (96 départements)"

# 4. Dépôt GitHub (public) et envoi
if ! gh repo view "$DEPOT" >/dev/null 2>&1; then
  gh repo create "$DEPOT" --public \
    --description "Comparateur d'occupation du sol (NAC INSP) : OCS GE, bases régionales et Fichiers fonciers, 96 départements"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$DEPOT.git"
git config http.postBuffer 524288000
echo "Envoi en cours (environ 500 Mo, plusieurs minutes selon la connexion)…"
git push -u origin main

# 5. GitHub Pages en mode « GitHub Actions »
gh api -X POST "repos/$DEPOT/pages" -f build_type=workflow >/dev/null 2>&1 \
  || gh api -X PUT "repos/$DEPOT/pages" -f build_type=workflow >/dev/null 2>&1 \
  || echo "Activez Pages à la main : Settings > Pages > Source : GitHub Actions"

# 6. Lancer la publication (le premier push a pu partir avant l'activation de Pages)
sleep 5
gh workflow run pages.yml >/dev/null 2>&1 || true
echo
echo "Suivi de la publication :  gh run watch   (ou onglet Actions du dépôt)"
echo "Site, d'ici quelques minutes : https://lucas-vivier.github.io/comparateur-artificialisation/"
