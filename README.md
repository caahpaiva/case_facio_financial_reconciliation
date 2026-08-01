# Case Facio - Financial Reconciliation

Este projeto realiza a conciliação entre os dados da Facio e dos Fundos, respondendo às 5 questões do case.

## Estrutura
- `scripts/validate_and_clean.py` → limpeza e normalização dos dados
- `analysis/reconciliation.py` → conciliação final e geração de KPIs
- `notebooks/01_reconciliation_analysis.ipynb` → análises e gráficos
- `outputs/` → resultados, KPIs, amostras e figuras

## Principais Resultados
- Total linhas: 49.999
- Match Exact: 15.442
- Match Divergent: 25.253
- Only Fundo: 9.295
- Only Facio: 9
- VP Facio: R$ 9.120.573,86
- VP Fundo: R$ 9.056.501,02
- Total abs diff: R$ 1.545.850,23

## Gráficos
Todos os gráficos foram gerados nas cores da Facio (azul e verde), conforme o enunciado.

## Como rodar
```bash
# ativar ambiente
source ./source/Scripts/activate

# rodar limpeza
python -m scripts.validate_and_clean

# rodar conciliação
python -m analysis.reconciliation

# abrir notebook
jupyter notebook notebooks/01_reconciliation_analysis.ipynb
