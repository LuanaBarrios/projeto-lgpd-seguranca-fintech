# Briefing do dashboard (Fase 3) — Aurora Pay

Contexto: projeto de portfólio de privacidade e segurança (LGPD) de uma fintech FICTÍCIA. O dashboard cruza o **risco de privacidade** (matriz da Fase 1) com os **incidentes detectados** (alertas da Fase 2). Todos os dados são sintéticos.

Ferramenta: Power BI. Idioma do dashboard: português do Brasil.

## 1. Tabelas (pasta `03-dashboard/modelo/`, CSV UTF-8)
| Tabela | Chave | Descrição |
|---|---|---|
| `dim_risco` | risco_id | 11 riscos (R01–R11): probabilidade, impacto, score, nivel, nivel_ordem, qtd_alertas, tem_evidencia |
| `fato_alertas` | alerta_id | 13 alertas: risco_id, usuario_ou_origem, tipo_origem, inicio (data e hora), data, hora, fora_do_expediente, severidade, evidencia |
| `dim_inventario` | dado_id | 15 categorias de dados pessoais: finalidade, base_legal_proposta, dado_sensivel, sistemas, quem_acessa, retencao_proposta |
| `ponte_risco_dado` | risco_id + dado_id | liga riscos a categorias de dados (muitos para muitos) |
| `dim_data` | Data | criar em DAX (ver abaixo) |

## 2. Relações
- `dim_risco[risco_id]` 1 → * `fato_alertas[risco_id]`
- `dim_risco[risco_id]` 1 → * `ponte_risco_dado[risco_id]`
- `dim_inventario[dado_id]` 1 → * `ponte_risco_dado[dado_id]`
- `dim_data[Data]` 1 → * `fato_alertas[data]`
- Direção do filtro: única (da dimensão para o fato). Ocultar chaves e colunas técnicas.
- Ordenar `dim_risco[nivel]` por `nivel_ordem`.

## 3. Medidas DAX
```
Total Riscos = COUNTROWS(dim_risco)
Total Alertas = COUNTROWS(fato_alertas)
Riscos Críticos e Altos = CALCULATE([Total Riscos], dim_risco[nivel] IN {"Crítico","Alto"})
Riscos com Evidência = CALCULATE([Total Riscos], dim_risco[tem_evidencia] = "Sim")
Riscos sem Evidência = CALCULATE([Total Riscos], dim_risco[tem_evidencia] = "Não")
% Cobertura de Detecção = DIVIDE([Riscos com Evidência], [Total Riscos])
Score Médio = AVERAGE(dim_risco[score])
Alertas Fora do Expediente = CALCULATE([Total Alertas], fato_alertas[fora_do_expediente] = "Sim")
Dados Sensíveis = CALCULATE(COUNTROWS(dim_inventario), dim_inventario[dado_sensivel] = "Sim")
```
Tabela de datas: `dim_data = CALENDAR(DATE(2026,8,1), DATE(2026,10,31))`, com colunas Mês e Dia da semana.

## 4. Páginas
1. **Visão executiva**: cartões ([Total Riscos], [Riscos Críticos e Altos], [Total Alertas], [% Cobertura de Detecção]); matriz de calor probabilidade × impacto (linhas = impacto, colunas = probabilidade, valor = contagem de riscos, cor pelo score); barras de riscos por nível.
2. **Riscos × incidentes** (a página principal): barras horizontais de score por risco, com [Total Alertas] ao lado (ou tabela com formatação condicional); destaque para riscos SEM evidência (R07 a R11) — em especial R11, nível Alto sem monitoramento. Segmentador por nível.
3. **Linha do tempo**: alertas por data (colunas), com tipo de risco na legenda; tabela de detalhe (risco, origem, data, evidência) filtrável; cartão de [Alertas Fora do Expediente].
4. **Inventário de dados (LGPD)**: matriz de base legal × categoria; cartão [Dados Sensíveis]; ao selecionar um risco, mostrar as categorias de dados afetadas (via ponte).

## 5. Estilo
- Tema escuro sóbrio ou claro limpo, no mesmo estilo das 4 páginas; fonte Segoe UI.
- Cores semânticas de nível: Crítico vermelho (#C0392B), Alto laranja (#E67E22), Médio amarelo (#F1C40F), Baixo verde (#27AE60). Neutros em cinza para o resto.
- Título de cada página diz a conclusão (ex.: "6 de 11 riscos têm evidência; 5 ainda sem monitoramento").
- Rodapé: "Dados sintéticos — projeto de portfólio".

## 6. Regras
- Não inventar números: todo valor vem das tabelas acima.
- O dashboard NÃO usa o arquivo GABARITO.
- Se o MCP só consegue editar o modelo (tabelas, relações, medidas) e não os visuais, criar o modelo e as medidas e deixar as páginas descritas na seção 4 para montagem manual.
