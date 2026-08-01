# case_facio_financial_reconciliation

Repositório para conciliação financeira entre a posição interna da Facio e a posição reportada pelo gestor do fundo.

## Estrutura
- `data/processed/` : arquivos tratados (facio_tratado.csv, fundo_tratado.csv)
- `analysis/` : scripts de conciliação e plots
- `notebooks/` : notebook interativo
- `outputs/` : resultados gerados (CSV, JSON, PNG)
- `docs/` : resumo executivo e playbook operacional

## Como rodar (a partir dos dados tratados)
1. Coloque `facio_tratado.csv` e `fundo_tratado.csv` em `data/processed/`.
2. Crie ambiente virtual e instale dependências:
