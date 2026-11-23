# Fase 2 — Análise de logs da Aurora Pay (fictícia)

> Todos os dados são **sintéticos** e a empresa é **fictícia**.

## Resumo

Um script em Python (`detectar_anomalias.py`) aplica uma regra para cada risco da matriz que pode ser observado nos logs (R01 a R06) e gera `alertas_detectados.csv`. Foram encontrados **13 alertas**, todos com severidade Alta ou Crítica:

| Risco | Alertas | Quem / origem | Severidade |
|---|---|---|---|
| R01 Acesso indevido a dados de clientes | 1 | `u004` (Atendimento) | Crítico |
| R02 Exfiltração em massa por exportação | 1 | `u013` (Dados) | Crítico |
| R03 Credential stuffing na API | 1 | 3 IPs externos contra `api_publica` | Crítico |
| R04 Abuso de API por parceiro | 1 | `parceiro_lojaX` | Alto |
| R05 Conta de ex-funcionário ativa | 1 | `u001` (desligamento em 15/09) | Crítico |
| R06 Tomada de conta (account takeover) | 8 | 8 clientes | Crítico |

## Como rodar

```bash
pip install pandas
python 02-analise-logs/detectar_anomalias.py
```

O script imprime o diagnóstico de qualidade dos dados, a quantidade de alertas por risco e grava `02-analise-logs/alertas_detectados.csv` com as colunas `risco, usuario_ou_origem, inicio, evidencia, severidade`.

## Metodologia

### 1. Dados e qualidade

| Arquivo | Linhas | Nulos | Duplicados | Datas |
|---|---|---|---|---|
| logs_acesso.csv | 34.890 | 11.633 em `cliente_id` (esperado: login, deploy etc. não têm cliente) | 0 | todas válidas (03/08 a 30/10/2026) |
| transacoes.csv | 60.032 | nenhum | 0 | todas válidas (01/08 a 31/10/2026) |
| funcionarios.csv | 40 | 39 em `data_desligamento` (esperado: só 1 desligada) | 0 | — |
| clientes.csv | 5.000 | nenhum | 0 | — |

Os dados não precisaram de limpeza. As datas de transações têm nanossegundos e são lidas no formato ISO 8601.

### 2. O que é "normal" (linha de base)

Os limites das regras foram **calculados a partir dos próprios dados**, e não escolhidos à mão:

- **Rede interna:** todos os acessos de funcionários vêm de `10.20.x.x`. Os demais IPs são tratados como externos.
- **Expediente:** são as horas que concentram pelo menos 0,5% dos eventos internos de funcionários. O cálculo resultou em **8h às 19h59, de segunda a sexta**.
- **Clientes VIP:** são **2%** da base.

### 3. Regras por risco

| Risco | Evidência esperada (matriz) | Regra implementada | Justificativa do limite |
|---|---|---|---|
| **R01** | Consultas sem relação com a rotina | Para cada funcionário e dia, compara os VIPs distintos consultados com o esperado (consultas do dia × 2%). Marca o dia se P(acaso) < 0,001 (Poisson) e alerta se houver **≥ 2 dias** marcados | Quem atende uma fila "ao acaso" consulta ~2% de VIPs. Exigir 2 dias separa um padrão de um dia azarado |
| **R02** | Exportações grandes fora do horário ou de IP externo | Exportação com volume > Q3 + 3×IQR **e** (fora do expediente **ou** IP externo). Exportações com menos de 1h de intervalo formam um único episódio | Cerca de Tukey para valores extremos: **836 registros**, contra uma mediana de 224 |
| **R03** | Pico de falhas seguido de sucessos, poucos IPs | IP externo com mais de **20 falhas de login/hora** e algum login bem-sucedido depois. IPs simultâneos formam uma única campanha | O funcionário que mais errou a senha errou 4 vezes em 3 meses; o limite é 5 × 4, numa única hora |
| **R04** | Consultas sequenciais e regulares acima da média | Consultas/hora acima do **p99 humano (3/h)** **e** coeficiente de variação (CV) dos intervalos **< 0,1** | Há um só parceiro, então a comparação é com o comportamento humano. Intervalos quase constantes indicam automação |
| **R05** | Acessos após `data_desligamento` | Qualquer evento em data **posterior** ao desligamento (o próprio dia é tolerado). A severidade sobe com IP externo e/ou fora do expediente | Regra objetiva, sem limite estatístico |
| **R06** | Novo dispositivo + sequência de Pix em minutos | Dispositivo que aparece depois do primeiro dispositivo do cliente, com **≥ 3 Pix em 30 min** somando **> 10×** o maior valor anterior do cliente | Só 1% dos Pix do mesmo cliente ocorrem a menos de ~2,4h do anterior |

Os riscos R07 a R11 **não são observáveis** nestes logs ou ficam para outra análise (fornecedor, processo, consentimento, retenção, DWH).

A coluna `transacoes.fraude_flag` **não** foi usada para detectar nada, porque seria usar a resposta como pergunta. O arquivo `GABARITO_incidentes_plantados.csv` não foi aberto durante a análise.

## Achados

1. **R01 — `u004` (Atendimento):** em 6 dias (15/09, 17/09, 30/09, 01/10, 15/10 e 27/10), consultou 36 clientes VIP distintos, contra ~2,2 esperados (menor p = 3,4×10⁻⁷). VIPs representam 6,2% das consultas dessa pessoa, contra 2% da base. O padrão se repete: blocos de 6 consultas VIP no mesmo dia.
2. **R02 — `u013` (Dados):** em 11/10 (domingo), entre 02h17 e 02h33, fez 5 exportações do DWH somando **22.701 registros** a partir do IP externo `187.45.12.9`. Uma exportação normal tem cerca de 224 registros.
3. **R03 — campanha contra `api_publica`:** em 23/09, das 03h00 às 04h50, os IPs `185.220.101.7`, `91.240.118.22` e `45.155.205.10` geraram **900 falhas de login** (pico de 199/h por IP) e **12 logins bem-sucedidos** logo depois. Isso indica que credenciais vazadas funcionaram.
4. **R04 — `parceiro_lojaX` (`200.17.44.31`):** em 20/10, fez 300 consultas a 290 clientes distintos em 3,3h, **uma a cada 40 s exatos** (CV = 0,00). O pico foi de 90/h, contra 3/h de um humano.
5. **R05 — `u001`:** desligamento registrado em 15/09, mas a conta fez **45 consultas no CRM** em 28/09, 06/10 e 19/10, sempre às 23h e do IP externo `177.12.99.4`. É uma conta não revogada e usada fora da empresa.
6. **R06 — 8 clientes** (C02778, C04095, C02087, C01301, C00631, C03575, C02821, C03796): um dispositivo nunca visto fez de 3 a 6 Pix em 6 a 15 minutos, de madrugada, somando **R$ 10 mil a R$ 24 mil**. O maior valor anterior desses clientes era de no máximo ~R$ 430.

### Recomendações imediatas (ligadas à matriz de risco)

- **R05:** revogar a conta de `u001` e trocar a revisão trimestral por desligamento automático, integrado ao RH.
- **R03:** limitar tentativas por IP (rate limit) com bloqueio progressivo, e forçar a troca de senha das 12 contas acessadas.
- **R06:** reter ou confirmar transações de dispositivo novo e avisar os 8 clientes. Avaliar a comunicação de incidente à ANPD e aos titulares (art. 48 da LGPD).
- **R02:** limitar o volume de exportação, bloquear o DWH fora da rede interna e apurar o caso de `u013`.
- **R01:** apurar a conduta de `u004` e criar um alerta de consulta atípica a VIPs.
- **R04:** criar cota por chave de API e revisar o contrato com `parceiro_lojaX`.

## Análise de sensibilidade do R01

Como o R01 é a regra mais estatística, testamos o que muda quando o limite é afrouxado. O número entre parênteses é a quantidade de dias marcados.

| Limite de P(acaso) | Mín. 1 dia | Mín. 2 dias (usado) | Mín. 3 dias |
|---|---|---|---|
| **< 0,001** (usado) | u004 (6) | **u004 (6)** | u004 (6) |
| < 0,01 | u004 (6), u025 (1), u031 (1), u038 (1) | u004 (6) | u004 (6) |
| < 0,05 | 22 usuários | 13 usuários | 7 usuários |

Leitura:
- **O achado é estável:** com o limite usado (< 0,001), só `u004` é marcado, exija-se 1, 2 ou 3 dias. Os dias dessa pessoa têm probabilidade da ordem de 10⁻⁷, muito distante do limite.
- **O mínimo de 2 dias funciona como proteção:** a < 0,01, entram três usuários com um único dia marcado cada, provavelmente por acaso. Exigir 2 dias os remove.
- **A < 0,05 a regra perde utilidade.** São milhares de pares usuário-dia testados; com 5% de chance por teste, dezenas de dias passam por puro acaso. Esse é o problema de **comparações múltiplas**, e por isso o limite precisa ser rigoroso.

## Limitações e possíveis falsos positivos

1. **Dados sintéticos são mais regulares que os reais.** Há consultas exatamente a cada 40 segundos (R04), acessos a cada 60 s começando às 23h00 em ponto (R05), exportações a cada 4 min (R02) e Pix a cada 3 min (R06). Em produção, um robô costuma adicionar uma espera aleatória, e seria preciso detectar **regularidade aproximada**. A regra atual do R04 (CV < 0,1) não pegaria um robô com espera aleatória de 20 a 60 s (CV ≈ 0,3). Nos dados, o 1% de funcionários mais regulares tem CV de 0,51 e a mediana é 0,94. Um limite de ~0,35, combinado com outros sinais (proporção de clientes distintos, ausência de pausas, atividade contínua por horas), seria mais robusto.
2. **O analista soube previamente o número de linhas do gabarito (13)**, porque essa informação está no `dados/LEIAME.md`. Isso pode ter influenciado a decisão de agrupar os alertas em **um por caso** (por exemplo, os 6 dias de `u004` viram 1 alerta, e as 45 consultas de `u001` também). As regras e os limites vieram só dos dados de logs, transações, funcionários e clientes. A validação contra o gabarito será feita **pelo conteúdo** (usuário, data, origem), e não pela contagem de alertas.
3. **R01 — consultas a VIPs podem ser legítimas:** um atendente pode estar designado a uma carteira VIP ou a um projeto específico. A regra também só enxerga VIPs; um acesso indevido a clientes comuns (vizinho, parente) não seria detectado.
4. **R02 — trabalho remoto e cargas planejadas:** VPN, home office ou uma carga noturna autorizada geram IP externo ou horário atípico. É preciso cruzar com chamados e autorizações.
5. **R03 — IPs compartilhados:** NAT de operadora ou proxy corporativo concentram muitos usuários legítimos num só IP. O limite de 20/h é generoso, mas não é imune a isso.
6. **R04 — integrações legítimas também são regulares:** uma sincronização contratada pode ter intervalo fixo. A regra precisa ser comparada com a cota do contrato, que não existe nestes dados.
7. **R05 — fuso e o dia do desligamento:** acessos no próprio dia foram tolerados. Um acesso indevido nesse dia passaria despercebido.
8. **R06 — troca legítima de celular:** um cliente que troca de aparelho e paga contas em sequência pode ser marcado. O limite de 10× o maior valor anterior reduz esse risco, mas clientes com pouco histórico ficam mais expostos a falso positivo.
9. **Expediente fixo:** a definição de expediente não considera feriados, plantões nem as equipes de TI e Antifraude, que podem trabalhar fora do horário.
10. **Só o que está no log:** riscos de fornecedor, de processo e de consentimento (R07 a R11) não são cobertos por esta análise.
