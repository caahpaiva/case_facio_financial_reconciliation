import pandas as pd
from pathlib import Path

ROOT = Path.cwd()
DATA_DIR = ROOT / "data"


fundo = pd.read_parquet(DATA_DIR / "posicao_fundo.parquet")
facio = pd.read_parquet(DATA_DIR / "posicao_facio.parquet")

fundo.to_csv(DATA_DIR / "posicao_fundo.csv", index=False)
facio.to_csv(DATA_DIR / "posicao_facio.csv", index=False)