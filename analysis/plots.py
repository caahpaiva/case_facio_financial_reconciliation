# analysis/plots.py
from pathlib import Path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

ROOT = Path.cwd()
OUTPUT = ROOT / "outputs"
FIG_DIR = OUTPUT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
PALETTE = {'primary':'#0B3D91','teal':'#00A6A6','muted':'#6B7280','accent':'#F59E0B'}

def plot_rate_diff_by_product(merged):
    mask = (~merged['i_diff'].isna())
    if mask.sum() == 0:
        return
    plt.figure(figsize=(10,6))
    sns.boxplot(x='produto', y='i_diff', data=merged.loc[mask], palette='Set2')
    plt.title('Diferença de taxa por produto (i_fundo - i_facio)')
    plt.ylabel('Diferença de taxa diária')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'rate_diff_by_product.png', dpi=150)
    plt.close()
