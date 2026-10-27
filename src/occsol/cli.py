"""Ligne de commande : `occsol --help`."""
from __future__ import annotations

import typer

from . import download as dl
from .paths import TABLES

app = typer.Typer(help="OCS GE / MOS : téléchargement, classement, simulations.")


@app.command()
def lister(dep: str, ressource: str = "ocsge"):
    """Produits disponibles pour un département (ressource : ocsge, artif, artif_exemptions, pv)."""
    for p in dl.lister(dep, ressource):
        typer.echo(f"{p.kind:10} {p.annee:10} {p.nom}")


@app.command()
def telecharger(dep: str, ressource: str = "ocsge", kind: str = "millesime", annee: str = typer.Option(None)):
    """Télécharge un produit (le plus récent si plusieurs)."""
    typer.echo(dl.obtenir(dep, ressource, kind, annee))


@app.command()
def valider(dep: str, annee: str):
    """Compare le classement recalculé (scénario de référence) à la couche officielle."""
    from . import io
    from .nomenclature import classer
    off = io.artif_officiel(dep, annee)
    me = classer(off.drop(columns=["artif"]))
    ha = off.area / 1e4
    ok = me["artif"] == off["artif_officiel"]
    typer.echo(f"Accord en surface : {ha[ok].sum() / ha.sum():.4%} | "
               f"artificialisé officiel {ha[off.artif_officiel].sum():,.0f} ha, "
               f"recalculé {ha[me.artif].sum():,.0f} ha")


@app.command()
def simuler(dep: str, annees: str = "2018,2021,2024", scenarios: str = typer.Option(None)):
    """Stocks et flux par commune pour chaque scénario de config/scenarios.yaml."""
    from . import simulation as sim
    noms = scenarios.split(",") if scenarios else None
    st = sim.simuler(dep, annees.split(","), noms)
    fl = sim.flux_scenarios(st)
    TABLES.mkdir(parents=True, exist_ok=True)
    st.to_csv(TABLES / f"stocks_{dep}.csv", index=False)
    fl.to_csv(TABLES / f"flux_{dep}.csv", index=False)
    tot = fl.groupby(["scenario", "periode"])["ha_an"].sum().unstack().round(1)
    typer.echo(tot.to_string())


if __name__ == "__main__":
    app()
