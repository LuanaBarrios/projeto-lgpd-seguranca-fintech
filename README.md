# Segurança e privacidade de uma fintech (projeto de portfólio)

Projeto de portfólio em **privacidade e segurança de dados (LGPD)**, aplicado a uma fintech **fictícia** chamada **Aurora Pay** (carteira digital e crédito pessoal).

> **Aviso:** todos os dados deste repositório são **sintéticos** e a empresa é **fictícia**. Qualquer semelhança com pessoas ou CPFs reais é coincidência. As bases legais e os prazos de retenção são **propostas didáticas**, não aconselhamento jurídico.

## Objetivo
Simular, de ponta a ponta, o trabalho de um(a) analista de privacidade e segurança: mapear os dados pessoais tratados, avaliar riscos, encontrar evidências de incidentes nos logs e comunicar tudo em um painel.

## A empresa fictícia
**Aurora Pay** é uma instituição de pagamento pequena. Trata CPF, renda, histórico financeiro, score de crédito, biometria facial e transações, o que a torna um bom cenário de risco alto, com decisões automatizadas (art. 20 da LGPD) e forte ligação com fraude.

## Fases do projeto
| Fase | Pasta | O que entrega | Status |
|---|---|---|---|
| 1. Mapeamento LGPD | `01-mapeamento-lgpd/` | Inventário de dados (15 itens, com base legal) e matriz de risco (11 riscos) | Pronta |
| 2. Análise de logs | `02-analise-logs/` | Análise em Python dos logs de acesso para detectar anomalias que evidenciem os riscos | A fazer |
| 3. Dashboard | `03-dashboard/` | Painel cruzando risco de privacidade com incidentes detectados | A fazer |

## Dados (`dados/`)
Base sintética gerada com seed fixa (reproduzível). Período: 01/08/2026 a 31/10/2026.

- `clientes.csv`: 5.000 clientes
- `funcionarios.csv`: 40 usuários internos
- `transacoes.csv`: cerca de 60 mil transações
- `logs_acesso.csv`: cerca de 35 mil eventos de acesso
- `GABARITO_incidentes_plantados.csv`: incidentes inseridos de propósito, usados só para medir a análise da Fase 2 (não consultar antes de analisar)

Detalhes em `dados/LEIAME.md`.

## Como rodar
A Fase 2 usará Python 3 com pandas. As instruções de execução serão adicionadas em `02-analise-logs/` quando a fase for concluída.

## Metodologia
- **Risco** = probabilidade (1 a 5) × impacto (1 a 5). Baixo até 6, médio de 7 a 12, alto de 13 a 19, crítico a partir de 20.
- **Base legal**: indicada por artigo da LGPD em cada item do inventário.
