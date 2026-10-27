"""Bilan des départements traités par france_dep.py : rythmes OCS GE / Fichiers fonciers et contrôles automatiques."""
import json
from pathlib import Path
W = Path(__file__).resolve().parents[1] / "web"
R = [json.loads(p.read_text()) for p in sorted(W.glob("*/resume.json"))]
print(f"{len(R)} départements\n")
print("dep  période    OCS brut  OCS net  net corr.  FF      OCS/FF  web Mo  min  alertes")
tot = {"ocs": 0, "ff": 0}
for r in R:
    a = []
    if r["ff"] <= 0 or r["ocs_brut"] <= 0: a.append("rythme nul")
    q = r["ocs_brut"] / r["ff"] if r["ff"] else float("nan")
    if not (0.2 < q < 5): a.append("rapport hors 0,2-5")
    if r["ocs_net"] < 0: a.append("net négatif")
    if r["web_mo"] > 8: a.append("web lourd")
    if abs(sum(r["dest_ocs"].values()) - r["ocs_brut"]) > 0.05 * max(r["ocs_brut"], 1): a.append("destinations ≠ total")
    tot["ocs"] += r["ocs_brut"]; tot["ff"] += r["ff"]
    nc = r.get("ocs_net_corrige")
    print(f"{r['dep']:<4} {r['y1']}-{r['y2']}  {r['ocs_brut']:8.1f} {r['ocs_net']:8.1f} {('%.1f' % nc) if nc is not None else '-':>9} {r['ff']:7.1f} {q:6.2f} {r['web_mo']:6.1f} {r.get('minutes', 0):5.1f}  {', '.join(a)}")
print(f"\nTotal : OCS GE brut {tot['ocs']:.0f} ha/an ; Fichiers fonciers {tot['ff']:.0f} ha/an (périodes propres à chaque département)")
