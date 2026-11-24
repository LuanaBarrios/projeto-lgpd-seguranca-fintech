# Fase 3 — Dashboard de risco e conformidade (Aurora Pay)

> Empresa **fictícia** e dados **sintéticos**. Projeto de portfólio em segurança da informação e privacidade de dados (LGPD).

## Objetivo

Mostrar, em poucos segundos, **onde a Aurora Pay está exposta e onde ela não tem visibilidade**. O painel cruza:

- a **matriz de risco** da Fase 1: 11 riscos de privacidade e segurança, com probabilidade × impacto e um controle recomendado para cada um;
- os **13 alertas** que a análise de logs da Fase 2 detectou;
- o **inventário de dados pessoais**: 15 categorias, com a base legal da LGPD.

A pergunta central é: *os riscos que a empresa considera mais graves deixam evidência nos logs, e o que os logs já mostram?*

## Páginas

| Página | Pergunta que responde | O que mostra |
|---|---|---|
| **1. Visão executiva** | Qual é o tamanho do problema e onde ele se concentra? | Riscos mapeados, riscos críticos ou altos, alertas detectados e cobertura de detecção (o tooltip lista os riscos com regra de detecção implementada). Matriz de risco 5 × 5 completa (probabilidade × impacto) e alertas por risco, com cor por nível. |
| **2. Riscos × incidentes** | Quais riscos geraram evidência e quais seguem sem evidência nos logs? | Score de cada risco e tabela de riscos × alertas com o **controle recomendado** de cada risco. O ponto cego R11 aparece destacado, e as linhas com 0 alertas ficam apagadas. Filtro por nível e nota sobre riscos não observáveis em logs. |
| **3. Linha do tempo** | Quando os incidentes aconteceram e com que padrão? | Alertas por data, com cor por nível do risco, e alertas fora do expediente (a definição está no subtítulo). A tabela de detalhe mostra a **severidade do alerta** e o **nível do risco** lado a lado, com a evidência completa de cada caso. Filtro por risco. |
| **4. Inventário de dados (LGPD)** | Que dados pessoais estão em jogo, com que base legal, e quais riscos os afetam? | Matriz base legal × categoria e categorias sensíveis. O filtro começa em "Todos"; ao escolher um risco, aparecem as categorias de dados afetadas. Uma nota aponta as categorias sem risco mapeado. |

O menu lateral navega entre as páginas. O botão **⟲ Limpar filtros** zera os segmentadores.

### Termos usados no painel

- **Sem evidência nos logs:** o risco não gerou nenhum alerta na análise de logs da Fase 2. Isso **não** quer dizer que o risco não existe; quer dizer que os logs analisados não o mostram.
- **Ponto cego:** risco Crítico ou Alto sem evidência nos logs. Falta telemetria (registro de eventos) para detectá-lo. Hoje só o R11 entra nessa regra, que é calculada a partir dos dados (`dim_risco[ponto_cego]`).
- **Não observável em logs:** R07 (fornecedor de KYC) e R09 (processo de revisão humana de crédito) não deixam rastro em logs de acesso. O controle deles é contratual ou de processo.
- **Fora do expediente:** alerta cujo início foi **antes das 8h, a partir das 20h ou em fim de semana**. O expediente (segunda a sexta, 8h às 19h59) foi inferido dos próprios logs na Fase 2: são as horas com pelo menos 0,5% dos eventos internos de funcionários. A regra bate com os 11 de 13 alertas marcados no modelo.
- **Severidade do alerta × nível do risco:** a severidade é a gravidade de **um caso detectado** (Fase 2). O nível vem da **matriz**, pela probabilidade × impacto do risco (Fase 1). Um risco Médio pode gerar um alerta de severidade Crítica, como uma conta de ex-funcionário usada de madrugada.

## Principais achados

1. **Cobertura de detecção de 55%.** Só 6 dos 11 riscos (R01 a R06) têm regra de detecção implementada e geraram evidência nos logs. Os outros 5 (R07 a R11) seguem sem evidência nos logs.
2. **Tomada de conta (R06) é o risco que se materializou.** É o único risco Crítico (score 20) e concentra **8 dos 13 alertas** (62%): dispositivo novo seguido de Pix em minutos.
3. **R11 é o ponto cego.** "Dados pessoais completos no data warehouse" tem score 16, o mesmo de R01 e R03, que geraram alertas, mas falta telemetria para detectá-lo. Controle sugerido: pseudonimizar CPF e contato no DWH e registrar quem consulta.
4. **11 de 13 alertas ocorreram fora do expediente.** Os incidentes acontecem quando ninguém está olhando, o que justifica alertas automáticos 24×7 em vez de revisão manual.
5. **O único dado sensível (biometria facial, art. 5º II e art. 11) depende de um risco de fornecedor.** O R07 não é observável nos logs internos. A mitigação é contratual: cláusulas de segurança, auditoria e aviso de incidentes.

**Ponto de atenção para a próxima versão da matriz:** 2 das 15 categorias do inventário, **Status de verificação (D07)** e **Dados de empregados (D13)**, não têm nenhum risco mapeado na `ponte_risco_dado`. Ou faltam riscos para elas (por exemplo, acesso indevido a dados de RH ou fraude na verificação de identidade), ou o risco delas é considerado baixo; de qualquer forma, isso precisa ser registrado.

## Controles recomendados

A coluna `controle_recomendado` (em `modelo/dim_risco.csv`) traz **sugestões** de controle prático para cada um dos 11 riscos. É uma proposta do projeto, não um plano auditado nem parecer jurídico. Ela aparece na tabela da página 2 (coluna "Controle sugerido") e no tooltip do gráfico de score.

## Como abrir

1. Instale o **Power BI Desktop** numa versão recente, com suporte a projetos `.pbip` e ao formato de relatório PBIR.
2. Abra `03-dashboard/dashboard_aurora_pay.pbip` e clique em **Atualizar** se o Power BI avisar que há tabelas sem dados ou objetos calculados para atualizar.
3. Se o projeto estiver em outra pasta, atualize o parâmetro da origem dos dados:
   - vá em **Página Inicial → Transformar dados → Editar parâmetros**;
   - em **PastaDados**, informe o caminho da pasta `03-dashboard/modelo/` **terminando com `\`**;
   - clique em **Atualizar**.
4. Para navegar pelo menu no modo de edição, use **Ctrl + clique** nos botões.

## Modelo de dados

```
dim_probabilidade (1–5) ──┐
dim_impacto (1–5) ────────┴─1:N──> dim_risco (11) ──1:N──> fato_alertas (13) <──N:1── dim_data (01/08–31/10/2026)
                                       │
                                       └──1:N──> ponte_risco_dado (31) <──N:1── dim_inventario (15)
```

- **Filtros:** em sentido único, da dimensão para o fato. A ponte é lida por medida (`Riscos que Afetam o Dado`), sem filtro bidirecional.
- **Grade da matriz:** `dim_probabilidade` e `dim_impacto` (de 1 a 5) fazem a matriz de risco mostrar as 25 células, mesmo as que não têm risco. Essas células ficam num tom apagado da cor da sua zona.
- **Pastas de medidas:** `1. Riscos`, `2. Alertas` e `3. Inventário LGPD`. Toda medida tem descrição.
- **Medidas auxiliares:** as de cor, contraste e tooltip ficam ocultas em `9. Auxiliares (formatação)`.
- **Tabela de datas:** `dim_data` está marcada como tabela de datas.
- **Cores semânticas de nível:** Crítico `#C0392B`, Alto `#E67E22`, Médio `#F1C40F`, Baixo `#27AE60`. A cor nunca é a única pista: nível e severidade também aparecem em texto (tabelas e tooltips). Na matriz, o número é branco sobre vermelho e escuro sobre amarelo, laranja e verde.
- **Textos de evidência:** gerados na origem pelo script da Fase 2, com moeda e decimais no padrão brasileiro (R$ 15.424,32; 6,2%) e sem jargão estatístico. No R01, por exemplo, "menor p=3.4e-07" virou "concentração muito acima do esperado (chance de ser acaso: menos de 1 em 1 milhão)".

## Limitações

- **Dados sintéticos.** A base foi gerada com seed fixa e tem padrões mais regulares que os reais. Os números ilustram o método, não uma empresa real.
- **"Sem evidência" não é "sem risco".** R07 (fornecedor) e R09 (processo) não são observáveis em logs de acesso. Para os demais, a ausência de alertas pode indicar falta de telemetria, não segurança.
- **Controles recomendados são sugestões.** Foram escritos como proposta didática para cada risco e precisariam ser validados com as áreas responsáveis.
- **Agrupamento dos alertas.** Cada alerta é um caso (por exemplo, os 6 dias de consultas atípicas de um funcionário contam como 1). As contagens dependem desse critério da Fase 2.
- **Caminho dos CSVs.** Os dados vêm de `03-dashboard/modelo/*.csv` pelo parâmetro `PastaDados`, que aponta para a pasta da máquina onde o projeto foi criado. Ao clonar, ajuste o parâmetro.
- **Títulos estáticos.** Os títulos das páginas são texto escrito a partir dos números do modelo. Se os CSVs mudarem, os gráficos se atualizam, mas os títulos precisam ser revisados à mão.
- **Bases legais propostas.** Os artigos da LGPD indicados são propostas didáticas, não parecer jurídico.
