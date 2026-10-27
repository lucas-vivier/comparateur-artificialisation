"""Piste A : liste les produits OCSGE / OCSGE-ARTIFICIALISATION par département (API Géoplateforme)."""
import csv, sys, time, xml.etree.ElementTree as ET
import requests
DEPS = ["75","77","78","91","92","93","94","95","02","59","60","62","80"]
RES = ["OCSGE-ARTIFICIALISATION", "OCSGE"]
A = "{http://www.w3.org/2005/Atom}"
def get(url, **kw):
    for i in range(5):
        try:
            r = requests.get(url, timeout=60, **kw); r.raise_for_status(); return r
        except Exception as e:
            print("retry", url, e, file=sys.stderr); time.sleep(5*(i+1))
    raise RuntimeError(url)
rows = []
for d in DEPS:
    z = f"D{d.zfill(3)}"
    for res in RES:
        root = ET.fromstring(get(f"https://data.geopf.fr/telechargement/resource/{res}", params={"zone": z, "limit": 50}).content)
        for e in root.iter(A+"entry"):
            t = e.find(A+"title").text
            if z in t:
                rows.append({"dep": d, "ressource": res, "produit": t})
w = csv.DictWriter(open(sys.argv[1], "w", newline=""), fieldnames=["dep","ressource","produit"]); w.writeheader(); w.writerows(rows)
for r in rows: print(r["dep"], r["ressource"], r["produit"])
