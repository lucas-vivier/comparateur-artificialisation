#!/bin/bash
# Boucle autonome : pilote puis reste de la France (départements sans base régionale). Reprenable.
cd /home/claude/occsol; export PYTHONPATH=src
PY=/home/claude/venv/bin/python; L=outputs/france; O=/mnt/user-data/outputs/france; mkdir -p $L $O/web
PILOTE="32 12 33 31 69 34 85 83 73 05"
DEJA="75 77 78 91 92 93 94 95 02 59 60 62 80 29 22"
TOUS=$(cut -d' ' -f1 $L/millesimes.txt)
RESTE=$(for d in $TOUS; do case " $PILOTE $DEJA " in *" $d "*) ;; *) echo $d;; esac; done)
for d in $PILOTE _pilote $RESTE; do
  if [ "$d" = _pilote ]; then $PY scripts/france_bilan.py > $L/bilan_pilote.txt 2>&1; cp $L/bilan_pilote.txt $O/; continue; fi
  [ -s web/$d/resume.json ] && continue
  for essai in 1 2; do
    echo "$(date +%T) debut $d essai $essai" >> $L/_progression.log
    timeout 3h $PY scripts/france_dep.py $d > $L/$d.log 2>&1 && break
    echo "$(date +%T) ECHEC $d essai $essai : $(tail -1 $L/$d.log)" >> $L/_progression.log
    rm -rf data/processed/$d data/raw/ocsge/france/*D0${d}_* 2>/dev/null
  done
  [ -s web/$d/resume.json ] && { echo "$(date +%T) ok $d $(cat web/$d/resume.json | cut -c1-160)" >> $L/_progression.log; rm -rf $O/web/$d; cp -r web/$d $O/web/; }
  cp $L/_progression.log $L/$d.log $O/ 2>/dev/null
done
$PY scripts/france_bilan.py > $L/bilan_france.txt 2>&1; cp $L/bilan_france.txt $O/
echo "$(date +%T) FIN" >> $L/_progression.log; cp $L/_progression.log $O/
