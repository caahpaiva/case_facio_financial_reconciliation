# analysis/reconciliation.py
"""
Conciliação final.
Entrada esperada: data/processed/facio_tratado.parquet, data/processed/fundo_tratado.parquet
  (fallback para .csv se o .parquet não existir, para compatibilidade com pipelines antigos)
Saídas: outputs/conciliation_results.csv,
        outputs/conciliation_results_with_rates.csv,
        outputs/kpis_summary.json,
        outputs/top10_divergences.csv,
        outputs/sample_only_facio.csv,
        outputs/sample_only_fundo.csv
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
import unicodedata
from analysis.normalization import normalize_key
from analysis.utils import (
    EPS_ABS,
    compute_implicit_rate,
    compute_vp,
    classify_reconciliation,
)

# --------------------------------------------------------------------------
# configuração
# ROOT ancorado no arquivo, não no cwd — mesmo padrão do validate_and_clean.py
ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"
FIG_DIR = OUTPUT / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# saída canônica do validate_and_clean.py é Parquet; CSV fica como fallback
FACIO_PARQUET = DATA_PROCESSED / "facio_tratado.parquet"
FUNDO_PARQUET = DATA_PROCESSED / "fundo_tratado.parquet"
FACIO_CSV = DATA_PROCESSED / "facio_tratado.csv"
FUNDO_CSV = DATA_PROCESSED / "fundo_tratado.csv"



logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATE_COLS = ["data_referencia", "data_cessao", "data_vencimento"]

NUMERIC_COLS = [
    "valor_cessao",
    "valor_nominal",
    "valor_presente_fundo",
    "valor_presente_calculado",
]




def read_processed(parquet_path: Path, csv_path: Path) -> pd.DataFrame:
    """Lê o arquivo tratado preservando tipo (Parquet) ou convertendo de CSV legado, normalizando datas e tipos numéricos."""
  
    if parquet_path.exists():
        logger.info("Lendo parquet: %s", parquet_path)
        df = pd.read_parquet(parquet_path)
        for d in DATE_COLS:
            if d in df.columns and pd.api.types.is_datetime64_any_dtype(df[d]):
                df[d] = df[d].dt.normalize()
        return df

    if csv_path.exists():
        logger.warning("Parquet não encontrado (%s); lendo CSV legado: %s", parquet_path, csv_path)
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[""])
        for d in DATE_COLS:
            if d in df.columns:
                df[d] = pd.to_datetime(df[d], errors="coerce").dt.normalize()
        for c in NUMERIC_COLS:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    raise FileNotFoundError(f"Nem parquet nem csv encontrados: {parquet_path} / {csv_path}")


def run_reconciliation(
    facio_parquet=FACIO_PARQUET,
    fundo_parquet=FUNDO_PARQUET,
    facio_csv=FACIO_CSV,
    fundo_csv=FUNDO_CSV,
    output_dir=OUTPUT,
):
    logger.info("Iniciando conciliação")

    facio = read_processed(facio_parquet, facio_csv)
    fundo = read_processed(fundo_parquet, fundo_csv)
    logger.info("Shapes lidos - Facio: %s, Fundo: %s", facio.shape, fundo.shape)

    facio["key"] = normalize_key(facio["key"])
    fundo["key"] = normalize_key(fundo["key"])

    # debug de chave (mantido do script original)
    debug_cols = ["id_contrato", "parcela", "parcela_z", "fundo", "fundo_code", "key"]
    facio[[c for c in debug_cols if c in facio.columns]].head(20).to_csv(
        output_dir / "facio_debug_key.csv", index=False
    )
    fundo[[c for c in debug_cols if c in fundo.columns]].head(20).to_csv(
        output_dir / "fundo_debug_key.csv", index=False
    )

    # calcular taxa implícita e VP no lado Facio
    required = {"valor_cessao", "valor_nominal", "data_vencimento", "data_cessao", "data_referencia"}
    if required.issubset(facio.columns):
        facio["dc_cessao"] = (facio["data_vencimento"] - facio["data_cessao"]).dt.days
        facio["t_ref"] = (facio["data_referencia"] - facio["data_cessao"]).dt.days
        facio["i_facio"] = compute_implicit_rate(
            facio["valor_cessao"].values, facio["valor_nominal"].values, facio["dc_cessao"].values
        )
        facio["valor_presente_calculado"] = compute_vp(
            facio["valor_cessao"].values, facio["i_facio"].values, facio["t_ref"].values, facio["dc_cessao"].values
        )
    else:
        missing = required - set(facio.columns)
        logger.warning("Colunas ausentes para calcular VP da Facio: %s — pulei o cálculo.", missing)

    # merge por key
    # (key + valor_presente_fundo)
    # parcela, fundo, fundo_code e data_referencia existem nos dois
     # eles (id_contrato_facio/id_contrato_fundo, ...), deixando o CSV final
    # sem uma coluna única para filtrar por contrato.
    fundo_slim = fundo[["key", "valor_presente_fundo"]].drop_duplicates(subset="key")

    merged = pd.merge(facio, fundo_slim, on="key", how="outer", indicator=True)

    # linhas que só existem no fundo não têm as demais colunas da Facio
    # (produto, fundo, datas, etc.) — isso é esperado e correto: elas de
    # fato não existem no arquivo da Facio. Trazemos ao menos `fundo` e
    # `fundo_code` do lado do fundo para essas linhas, para não perder a
    # informação de qual FIDC está reportando a parcela.
    only_fundo_mask = merged["_merge"] == "right_only"
    if only_fundo_mask.any():
        fundo_lookup = fundo.set_index("key")[["fundo", "fundo_code"]]
        merged.loc[only_fundo_mask, ["fundo", "fundo_code"]] = merged.loc[only_fundo_mask, "key"].map(
            lambda k: fundo_lookup.loc[k] if k in fundo_lookup.index else pd.Series({"fundo": pd.NA, "fundo_code": pd.NA})
        ).apply(pd.Series).values

    # classificação vetorizada (ver docstring de classify_reconciliation)
    merged["recon_status"] = classify_reconciliation(
        merged["_merge"].values,
        merged.get("valor_presente_calculado", pd.Series(np.nan, index=merged.index)).values,
        merged.get("valor_presente_fundo", pd.Series(np.nan, index=merged.index)).values,
    )

    # divergências — denominador único (VP do fundo), consistente com o
    # critério usado dentro de classify_reconciliation
    vp_facio_col = merged.get("valor_presente_calculado", pd.Series(np.nan, index=merged.index))
    vp_fundo_col = merged.get("valor_presente_fundo", pd.Series(np.nan, index=merged.index))
    merged["abs_diff"] = (vp_facio_col - vp_fundo_col).abs()
    merged["rel_diff"] = merged["abs_diff"] / vp_fundo_col.abs().clip(lower=1e-9)

    # exposição de referência: VP calculado da Facio; se a parcela só existe
    # no fundo, usamos o VP do fundo (única fonte disponível para ela)
    merged["valor_exposicao"] = vp_facio_col.fillna(vp_fundo_col)

    # KPIs
    kpis = {
        "total_rows": int(len(merged)),
        "counts_by_status": merged["recon_status"].value_counts().to_dict(),
        "vp_total_exposicao": float(merged["valor_exposicao"].sum(skipna=True)),
        "vp_total_facio": float(vp_facio_col.sum(skipna=True)),
        "vp_total_fundo": float(vp_fundo_col.sum(skipna=True)),
        "total_abs_diff_divergentes": float(
            merged.loc[merged["recon_status"] == "Match Divergent", "abs_diff"].sum(skipna=True)
        ),
    }

    # --- saídas ---------------------------------------------------------
    base_cols_out = output_dir / "conciliation_results.csv"
    rates_cols_out = output_dir / "conciliation_results_with_rates.csv"

    # versão enxuta: sem as colunas intermediárias de taxa/prazo
    rate_cols = ["dc_cessao", "t_ref", "i_facio"]
    merged.drop(columns=[c for c in rate_cols if c in merged.columns]).to_csv(base_cols_out, index=False)
    # versão completa: inclui taxa implícita, prazos e t_ref usados no cálculo
    merged.to_csv(rates_cols_out, index=False)

    merged.sort_values("abs_diff", ascending=False, na_position="last").head(10).to_csv(
        output_dir / "top10_divergences.csv", index=False
    )
    with open(output_dir / "kpis_summary.json", "w", encoding="utf-8") as fh:
        json.dump(kpis, fh, indent=2, default=str)

    merged[merged["_merge"] == "left_only"].head(200).to_csv(output_dir / "sample_only_facio.csv", index=False)
    merged[merged["_merge"] == "right_only"].head(200).to_csv(output_dir / "sample_only_fundo.csv", index=False)

    logger.info("Conciliação salva em: %s", output_dir)
    logger.info("KPIs: %s", kpis)

    return merged, kpis


if __name__ == "__main__":
    merged_df, summary_kpis = run_reconciliation()
    print("Conciliação finalizada. KPIs:", summary_kpis)