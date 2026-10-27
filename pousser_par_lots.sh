#!/usr/bin/env bash
# Envoie le dépôt sur GitHub en plusieurs petits envois (si le gros envoi unique reste bloqué).
# À lancer depuis le Terminal du Mac :  bash pousser_par_lots.sh
set -euo pipefail
cd "$(dirname "$0")"

git config http.postBuffer 157286400   # 150 Mo par requête

# 1. Défaire le commit unique (les fichiers restent intacts sur le disque)
if git rev-parse --verify -q HEAD >/dev/null && [ -z "$(git ls-remote --heads origin main)" ]; then
  git update-ref -d HEAD
  git rm -r -q --cached . >/dev/null
fi

# 2. Premier lot : tout sauf les départements du site
git add -A
git reset -q -- web/[0-9][0-9A-B]/ 2>/dev/null || true
git commit -q -m "Code, documentation et page du comparateur"
echo "Lot 1 : code et page"; git push -u origin main

# 3. Lots de 12 départements (environ 50 à 70 Mo chacun)
deps=$(ls -d web/[0-9][0-9AB]/ | sort)
lot=(); n=2
for d in $deps; do
  lot+=("$d")
  if [ ${#lot[@]} -eq 12 ]; then
    git add "${lot[@]}"; git commit -q -m "Données du comparateur : ${lot[0]%/} à ${lot[${#lot[@]}-1]%/}"
    echo "Lot $n : ${lot[0]} à ${lot[${#lot[@]}-1]}"; git push origin main; lot=(); n=$((n+1))
  fi
done
if [ ${#lot[@]} -gt 0 ]; then
  git add "${lot[@]}"; git commit -q -m "Données du comparateur : ${lot[0]%/} à ${lot[${#lot[@]}-1]%/}"
  echo "Lot $n : ${lot[0]} à ${lot[${#lot[@]}-1]}"; git push origin main
fi

git status -sb | head -3
echo "Terminé. Activation de Pages et publication :"
gh api -X POST "repos/lucas-vivier/comparateur-artificialisation/pages" -f build_type=workflow >/dev/null 2>&1 || true
sleep 5; gh workflow run pages.yml >/dev/null 2>&1 || true
echo "Suivi : gh run watch   —   Site : https://lucas-vivier.github.io/comparateur-artificialisation/"
