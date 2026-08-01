# Relatório de Conciliação Facio

## KPIs Gerais
- Total linhas: 49.999
- Match Exact: 15.442
- Match Divergent: 25.253
- Only Fundo: 9.295
- Only Facio: 9
- VP Facio: R$ 9.120.573,86
- VP Fundo: R$ 9.056.501,02
- Total abs diff: R$ 1.545.850,23

## Mapping de Fundos
- FACIO 3 → FIDC3
- FACIO 4 → FIDC4

# Resumo Executivo - Reconciliação de Carteira Facio

## Objetivo e metodologia

Foi realizada a reconciliação da carteira Facio versus posição dos fundos, com objetivo de identificar diferenças operacionais e financeiras entre as posições.

A metodologia aplicada contemplou:

- cálculo da taxa diária implícita de desconto de cada parcela utilizando:
  - valor de cessão;
  - data de cessão;
  - valor presente;
  - data de vencimento;

- cálculo do valor presente (VP) da carteira Facio na data de referência;

- comparação entre o VP calculado pela Facio e o VP informado pelo fundo;

- classificação das parcelas em uma taxonomia de reconciliação:

| Status | Critério |
|---|---|
| Match Exact | Parcela encontrada nos dois lados com diferença dentro do limite de tolerância |
| Match Divergent | Parcela encontrada nos dois lados, porém com divergência de valor presente |
| Only Facio | Parcela existente somente na posição Facio |
| Only Fundo | Parcela existente somente na posição do fundo |

---

# 1. Resultado da Reconciliação

A carteira analisada apresentou o seguinte resultado:

| Status | Quantidade | Exposição Financeira |
|---|---:|---:|
| Match Exact | 35.849 | R$ 6,64 milhões |
| Only Fundo | 9.295 | R$ 1,45 milhões |
| Match Divergent | 4.846 | R$ 1,15 milhões |
| Only Facio | 9 | R$ 1,0 mil |

O maior ponto de atenção identificado foi a existência de **9.295 registros presentes apenas na posição do fundo**, representando aproximadamente **R$ 1,45 milhões de exposição financeira não encontrada na carteira Facio**.

Esse comportamento sugere possíveis diferenças de:

- atualização entre sistemas;
- cutoff operacional;
- integração entre carteira e fundo;
- regras distintas de manutenção da posição.

Recomenda-se implementar uma reconciliação diária de existência dos ativos antes da comparação financeira.

---

# 2. Análise de Exposição Financeira

A exposição financeira por produto foi:

| Produto | Exposição |
|---|---:|
| SimpleCredit | R$ 5,38 milhões |
| SalaryAdvanceFX | R$ 2,33 milhões |
| eConsignado | R$ 72 mil |

O produto **SimpleCredit representa a maior concentração financeira da carteira**, seguido por SalaryAdvanceFX.

---

## Divergências de Valor Presente

Foram identificadas:

**4.846 parcelas com divergência financeira**

Distribuição das diferenças:

| Indicador | Valor |
|---|---:|
| Média | R$ 36,41 |
| Mediana | R$ 21,29 |
| 95º percentil | R$ 131,48 |
| Máxima divergência | R$ 911,94 |

A distribuição indica que a maior parte das divergências possui baixo impacto individual, porém existem outliers relevantes.

Os maiores desvios estão concentrados principalmente no:

- fundo: **FIDC4**
- produto: **SalaryAdvanceFX**

Principais ocorrências:

| Contrato | Produto | Fundo | Divergência |
|---|---|---|---:|
| CTR027641 | SalaryAdvanceFX | FIDC4 | R$ 911,94 |
| CTR011093 | SimpleCredit | FIDC4 | R$ 499,83 |
| CTR019269 | SimpleCredit | FIDC4 | R$ 412,95 |

Recomendação:

Criar regras automáticas de priorização:

- divergência > R$ 500 → investigação imediata;
- divergência > R$ 100 → análise operacional;
- demais divergências → acompanhamento estatístico.

---

# 3. Análise da Taxa Implícita do Fundo

Para os registros classificados como **Match Divergent**, foi calculada a taxa implícita utilizada pelo fundo.

Resultado consolidado:

| Indicador | Valor |
|---|---:|
| Taxa média Facio | 0,75% ao dia |
| Taxa média Fundo | -0,05% ao dia |
| Diferença média | -0,81 p.p. |

Foi identificado um comportamento sistemático onde o fundo utiliza uma taxa inferior à taxa calculada pela Facio.

---

## Diferença por Produto

| Produto | Diferença Média |
|---|---:|
| SimpleCredit | -1,64 p.p. |
| SalaryAdvanceFX | -0,57 p.p. |
| eConsignado | ≈ 0 |

O maior desvio ocorre no produto **SimpleCredit**, indicando possível diferença de convenção financeira.

---

## Diferença por Fundo

| Fundo | Diferença Média |
|---|---:|
| FIDC3 | -1,45 p.p. |
| FIDC4 | -0,68 p.p. |

O FIDC3 apresenta maior diferença relativa de metodologia.

Possíveis causas:

- taxa de desconto diferente;
- data-base distinta;
- tratamento de parcelas vencidas;
- regras diferentes de arredondamento.

Recomendação:

Criar uma documentação única de cálculo de VP entre Facio e fundos contendo:

- fórmula utilizada;
- taxa aplicada;
- data de referência;
- tratamento de vencidos;
- política de arredondamento.

---

# 4. Composição e Concentração do Portfólio

## Exposição por Fundo

| Fundo | VP |
|---|---:|
| FIDC4 | R$ 8,24 milhões |
| FIDC3 | R$ 989 mil |

Existe forte concentração no FIDC4, responsável por aproximadamente 89% da carteira.

---

## Exposição por Produto

| Produto | VP |
|---|---:|
| SimpleCredit | R$ 5,38 milhões |
| SalaryAdvanceFX | R$ 2,33 milhões |
| eConsignado | R$ 72 mil |

---

## Distribuição por Prazo

| Bucket | VP |
|---|---:|
| <30 dias | R$ 6,96 milhões |
| 30-90 dias | R$ 786 mil |
| 90-180 dias | R$ 18,8 mil |
| >180 dias | R$ 20,1 mil |

A carteira apresenta concentração significativa em vencimentos próximos.

---

## Duration Média Ponderada

A duration foi calculada utilizando prazo restante até vencimento ponderado pelo valor presente.

| Fundo | Duration |
|---|---:|
| FIDC3 | 34,7 dias |
| FIDC4 | 14,5 dias |

O FIDC4 possui carteira com prazo médio significativamente menor, indicando maior concentração em ativos de curto prazo.

---

## Percentual da carteira vencendo em até 30 dias

| Fundo | Percentual |
|---|---:|
| FIDC3 | 56,35% |
| FIDC4 | 77,68% |

O FIDC4 apresenta maior concentração de vencimentos no curto prazo, aumentando a necessidade de acompanhamento operacional.

---

# 5. Hipóteses de Causa Raiz e Plano de Remediação

## Only Facio

Foram encontrados:

**9 registros**

Distribuição:

| Produto | Fundo | Quantidade |
|---|---|---:|
| SimpleCredit | FIDC3 | 8 |
| SimpleCredit | FIDC4 | 1 |

Possíveis causas:

- atraso no envio ao fundo;
- diferença de cutoff;
- falha de integração.

Risco:

- ativos existentes na Facio sem reconhecimento pelo fundo.

---

# Only Fundo

Foram encontrados:

**9.295 registros**

Distribuição:

| Fundo | Quantidade |
|---|---:|
| FIDC4 | 5.264 |
| FIDC3 | 4.031 |

Como esses registros não possuem correspondência na Facio, o produto não pôde ser identificado.

Possíveis causas:

- carteira do fundo desatualizada;
- baixa ou substituição não refletida;
- divergência de chave de identificação.

Risco:

- exposição financeira registrada no fundo sem origem correspondente.

---

# Match Divergent

Principais concentrações:

| Produto | Fundo | Quantidade | Divergência Média |
|---|---|---:|---:|
| SalaryAdvanceFX | FIDC4 | 3.309 | R$ 32,66 |
| SimpleCredit | FIDC4 | 753 | R$ 58,01 |
| SimpleCredit | FIDC3 | 394 | R$ 37,92 |

O maior indício de diferença de convenção financeira está concentrado no produto **SimpleCredit**, principalmente nos fundos FIDC3 e FIDC4.

---

# Plano Operacional de Tratamento

| Categoria | Responsável | SLA | Escalonamento |
|---|---|---|---|
| Only Facio | Operações Facio | D+1 | Gestão Operacional |
| Only Fundo | Operações + Fundo | D+1 | Comitê Financeiro |
| Match Divergent | Financeiro + Dados | D+3 | Gestão de Risco |
| Divergência de taxa | Financeiro | D+5 | Diretoria |

---

# Recomendações Finais

1. Implementar reconciliação automática diária entre Facio e fundos.
2. Criar monitoramento de breaks por:
   - quantidade;
   - valor financeiro;
   - aging;
   - fundo;
   - produto.
3. Padronizar metodologia de cálculo de valor presente.
4. Criar alertas para divergências financeiras relevantes.
5. Monitorar concentração de vencimentos do FIDC4.
6. Revisar integração dos registros classificados como Only Fundo.

---

# Conclusão Executiva

A carteira apresenta boa conciliação financeira, com **35.849 registros classificados como Match Exact**, porém existem dois principais pontos de atenção:

**1. Diferença de posição entre sistemas**
- 9.295 registros aparecem apenas no fundo;
- representam R$ 1,45 milhões;
- indicam necessidade de melhoria no processo de integração e atualização.

**2. Diferença de metodologia financeira**
- 4.846 parcelas apresentam divergência de VP;
- diferenças estão concentradas em SimpleCredit e SalaryAdvanceFX;
- há indícios de utilização de convenção de taxa diferente pelo fundo.

A recomendação prioritária é estabelecer uma rotina diária de reconciliação automatizada, acompanhada de governança sobre divergências financeiras e padronização do cálculo de valor presente.
