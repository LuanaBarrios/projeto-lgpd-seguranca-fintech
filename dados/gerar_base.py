"""Gera a base sintética da fintech fictícia 'Aurora Pay' (projeto LGPD/segurança).
TODOS os dados são fictícios. Seed fixa para reprodutibilidade.
Saída: CSVs em OUT_DIR + gabarito dos incidentes plantados (separado).
"""
import sys, random
from pathlib import Path
import numpy as np
import pandas as pd
from faker import Faker

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
random.seed(42); np.random.seed(42)
fake = Faker("pt_BR"); Faker.seed(42)

N_CLI, N_FUNC = 5000, 40
INI, FIM = pd.Timestamp("2026-08-01"), pd.Timestamp("2026-10-31 23:59")

# ---------- clientes ----------
cli = []
for i in range(1, N_CLI + 1):
    nasc = fake.date_of_birth(minimum_age=18, maximum_age=75)
    renda = round(float(np.random.lognormal(8.2, 0.6)), 2)
    cli.append(dict(
        cliente_id=f"C{i:05d}", nome=fake.name(), cpf=fake.cpf(), email=fake.email(),
        telefone=fake.cellphone_number(), data_nascimento=nasc,
        cidade=fake.city(), uf=fake.estado_sigla(), renda_mensal=renda,
        score_credito=int(np.clip(np.random.normal(620, 130), 100, 1000)),
        biometria_facial=random.random() < 0.7,
        consentimento_marketing=random.random() < 0.55,
        status_kyc=random.choices(["aprovado", "pendente", "reprovado"], [0.9, 0.07, 0.03])[0],
        data_cadastro=fake.date_between(start_date="-3y", end_date="-30d"),
        vip=random.random() < 0.02,
    ))
cli = pd.DataFrame(cli)

# ---------- funcionários ----------
setores = {
    "Atendimento": ("Analista de Suporte", ["crm", "core"], 12),
    "Dados": ("Analista de Dados", ["dwh"], 5),
    "Antifraude": ("Analista de Fraude", ["antifraude", "core"], 5),
    "TI": ("Engenheiro de Software", ["core", "api", "dwh"], 8),
    "Financeiro": ("Analista Financeiro", ["core"], 4),
    "Compliance": ("Analista de Compliance", ["crm", "core", "antifraude"], 3),
    "Comercial": ("Analista de Marketing", ["crm"], 3),
}
func = []; k = 1
for setor, (cargo, sis, n) in setores.items():
    for _ in range(n):
        func.append(dict(usuario=f"u{k:03d}", nome=fake.name(), setor=setor, cargo=cargo,
                         sistemas_autorizados=";".join(sis),
                         status="ativo", data_desligamento=None)); k += 1
func = pd.DataFrame(func)
# usuário desligado com conta ainda ativa (incidente 5)
ex_idx = func[func.setor == "Atendimento"].index[0]
func.loc[ex_idx, "status"] = "desligado_conta_ativa"
func.loc[ex_idx, "data_desligamento"] = "2026-09-15"
EX_USER = func.loc[ex_idx, "usuario"]

# ---------- transações ----------
def rand_ts(n, start=INI, end=FIM, horario_comercial_bias=True):
    secs = (end - start).total_seconds()
    ts = start + pd.to_timedelta(np.random.uniform(0, secs, n), unit="s")
    return ts

N_TX = 60000
tx = pd.DataFrame(dict(
    cliente_id=np.random.choice(cli.cliente_id, N_TX),
    data_hora=rand_ts(N_TX),
    tipo=np.random.choice(["pix", "boleto", "cartao", "emprestimo", "transferencia"], N_TX, p=[.55, .15, .2, .03, .07]),
    valor=np.round(np.random.lognormal(4.3, 1.1, N_TX), 2),
    canal=np.random.choice(["app", "web", "api_parceiro"], N_TX, p=[.7, .2, .1]),
))
tx["dispositivo_id"] = "D" + tx.cliente_id.str[1:] + "-1"
tx["ip"] = [fake.ipv4_public() for _ in range(N_TX)]
tx["fraude_flag"] = False
tx["status"] = "concluida"

incidentes = []
extra_tx = []

# Incidente 6: account takeover — novo dispositivo + esvaziamento via Pix
for cid in random.sample(list(cli.cliente_id), 8):
    t0 = INI + pd.Timedelta(days=random.randint(5, 85), hours=random.randint(0, 5), minutes=random.randint(0, 59))
    ip = fake.ipv4_public()
    for j in range(random.randint(3, 6)):
        extra_tx.append(dict(cliente_id=cid, data_hora=t0 + pd.Timedelta(minutes=3 * j), tipo="pix",
                             valor=round(random.uniform(1500, 6000), 2), canal="app",
                             dispositivo_id=f"D-NOVO-{cid}", ip=ip, fraude_flag=True, status="concluida"))
    incidentes.append(dict(id="INC-06", tipo="account_takeover", usuario_ou_origem=cid, inicio=t0,
                           descricao="Dispositivo novo + sequência de Pix de alto valor em minutos"))
tx = pd.concat([tx, pd.DataFrame(extra_tx)], ignore_index=True).sort_values("data_hora")
tx.insert(0, "transacao_id", [f"T{i:06d}" for i in range(1, len(tx) + 1)])

# ---------- logs de acesso ----------
logs = []
def add(ts, usuario, sistema, acao, cliente=None, ip=None, volume=1, status="ok"):
    logs.append(dict(timestamp=ts, usuario=usuario, sistema=sistema, acao=acao,
                     cliente_id=cliente, ip_origem=ip, qtd_registros=volume, status=status))

ips_internos = {u: f"10.20.{random.randint(1,30)}.{random.randint(2,250)}" for u in func.usuario}
sis_acao = {"crm": ["consulta_cliente", "edicao_cadastro"], "core": ["consulta_saldo", "consulta_extrato"],
            "antifraude": ["analise_alerta", "consulta_cliente"], "dwh": ["query_agregada", "exportacao"],
            "api": ["deploy", "consulta_logs"]}

# tráfego normal: dias úteis, horário comercial
dias = pd.bdate_range(INI, FIM)
for u in func.itertuples():
    for d in dias:
        if u.status != "ativo" and d > pd.Timestamp("2026-09-15"):
            continue
        for _ in range(np.random.poisson(12)):
            sis = random.choice(u.sistemas_autorizados.split(";"))
            h = int(np.clip(np.random.normal(13, 3), 8, 19))
            ts = d + pd.Timedelta(hours=h, minutes=random.randint(0, 59), seconds=random.randint(0, 59))
            acao = random.choice(sis_acao[sis])
            add(ts, u.usuario, sis, acao, random.choice(cli.cliente_id) if sis in ("crm", "core", "antifraude") else None,
                ips_internos[u.usuario], 1 if acao != "exportacao" else random.randint(50, 400))
# logins
for u in func.itertuples():
    for d in dias:
        if u.status != "ativo" and d > pd.Timestamp("2026-09-15"):
            continue
        add(d + pd.Timedelta(hours=8, minutes=random.randint(0, 90)), u.usuario, "sso", "login_ok", ip=ips_internos[u.usuario])
        if random.random() < 0.03:
            add(d + pd.Timedelta(hours=8, minutes=random.randint(0, 90)), u.usuario, "sso", "login_falha", ip=ips_internos[u.usuario], status="falha")

# Incidente 1: snooping — analista de suporte consulta VIPs sem ticket
vips = list(cli[cli.vip].cliente_id)
snoop = func[func.setor == "Atendimento"].usuario.iloc[3]
for d in random.sample(list(dias[20:]), 6):
    for c in random.sample(vips, 6):
        add(d + pd.Timedelta(hours=random.randint(8, 18), minutes=random.randint(0, 59)), snoop, "crm", "consulta_cliente", c, ips_internos[snoop])
incidentes.append(dict(id="INC-01", tipo="acesso_indevido_interno", usuario_ou_origem=snoop, inicio="2026-09-01",
                       descricao="Consultas repetidas a clientes VIP sem relação com atendimento"))

# Incidente 2: exportação em massa fora do horário
dados_user = func[func.setor == "Dados"].usuario.iloc[0]
t0 = pd.Timestamp("2026-10-11 02:17")
for j in range(5):
    add(t0 + pd.Timedelta(minutes=4 * j), dados_user, "dwh", "exportacao", None, "187.45.12.9", random.randint(4000, 5000))
incidentes.append(dict(id="INC-02", tipo="exfiltracao_dados", usuario_ou_origem=dados_user, inicio=t0,
                       descricao="Exportações de ~25 mil registros às 2h de um domingo, IP externo"))

# Incidente 3: credential stuffing na API
ips_atk = ["45.155.205.10", "185.220.101.7", "91.240.118.22"]
t0 = pd.Timestamp("2026-09-23 03:00")
for j in range(900):
    add(t0 + pd.Timedelta(seconds=7 * j), "api_publica", "api", "login_falha", None, random.choice(ips_atk), status="falha")
for j in range(12):
    add(t0 + pd.Timedelta(seconds=7 * 900 + 30 * j), "api_publica", "api", "login_ok", None, random.choice(ips_atk))
incidentes.append(dict(id="INC-03", tipo="credential_stuffing", usuario_ou_origem=";".join(ips_atk), inicio=t0,
                       descricao="~900 falhas de login em ~1h e 12 sucessos a partir de 3 IPs"))

# Incidente 4: parceiro via API fazendo scraping de CPFs
t0 = pd.Timestamp("2026-10-20 09:00")
for j in range(300):
    add(t0 + pd.Timedelta(seconds=40 * j), "parceiro_lojaX", "api", "consulta_cliente", random.choice(cli.cliente_id), "200.17.44.31", 1)
incidentes.append(dict(id="INC-04", tipo="abuso_api_parceiro", usuario_ou_origem="parceiro_lojaX", inicio=t0,
                       descricao="Parceiro consulta 300 clientes sequencialmente, acima do contrato"))

# Incidente 5: conta de ex-funcionário ativa
for d in [pd.Timestamp("2026-09-28"), pd.Timestamp("2026-10-06"), pd.Timestamp("2026-10-19")]:
    for j in range(15):
        add(d + pd.Timedelta(hours=23, minutes=j), EX_USER, "crm", "consulta_cliente", random.choice(cli.cliente_id), "177.12.99.4")
incidentes.append(dict(id="INC-05", tipo="conta_desligado_ativa", usuario_ou_origem=EX_USER, inicio="2026-09-28",
                       descricao="Usuário desligado em 15/09 acessando o CRM à noite de IP externo"))

logs = pd.DataFrame(logs).sort_values("timestamp").reset_index(drop=True)
logs.insert(0, "log_id", [f"L{i:07d}" for i in range(1, len(logs) + 1)])

# ---------- salvar ----------
cli.to_csv(OUT / "clientes.csv", index=False)
func.to_csv(OUT / "funcionarios.csv", index=False)
tx.to_csv(OUT / "transacoes.csv", index=False)
logs.to_csv(OUT / "logs_acesso.csv", index=False)
pd.DataFrame(incidentes).to_csv(OUT / "GABARITO_incidentes_plantados.csv", index=False)
for n, d in dict(clientes=cli, funcionarios=func, transacoes=tx, logs_acesso=logs, incidentes=pd.DataFrame(incidentes)).items():
    print(n, d.shape)
