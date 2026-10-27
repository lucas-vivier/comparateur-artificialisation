"""Chemins du projet, résolus depuis la racine du dépôt."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_OCSGE = RAW / "ocsge"
RAW_MOS = RAW / "mos"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
FIGURES = OUTPUTS / "figures"
