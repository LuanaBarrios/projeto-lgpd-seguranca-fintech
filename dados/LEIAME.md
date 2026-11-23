# Aurora Pay (fictícia) — base sintética

Instituição de pagamento fictícia (carteira digital + crédito pessoal). **Todos os dados são sintéticos** (Faker pt_BR, seed 42). Período: 01/08/2026 a 31/10/2026.

## Arquivos
| Arquivo | Linhas | Conteúdo |
|---|---|---|
| clientes.csv | 5.000 | Dados pessoais: CPF, contato, nascimento, renda, score, biometria, consentimento, KYC, flag VIP |
| funcionarios.csv | 40 | Usuários internos, setor, sistemas autorizados, status (1 desligado com conta ativa) |
| transacoes.csv | ~60 mil | Pix, boleto, cartão, empréstimo, transferência; canal, dispositivo, IP, fraude_flag |
| logs_acesso.csv | ~35 mil | Acessos internos e via API: usuário, sistema, ação, cliente alvo, IP, volume, status |
| GABARITO_incidentes_plantados.csv | 13 | Respostas dos incidentes plantados. **Não abrir antes de fazer a análise (Fase 2).** |

## Sistemas nos logs
sso, crm, core (core bancário), antifraude, dwh (data warehouse), api.

## Incidentes plantados (6 tipos) — descobrir pela análise, sem olhar o gabarito
Para você descobrir nos logs e transações. O gabarito serve para medir o quanto o seu script acertou.
