"""
Fase 2 - Detecção de anomalias nos logs da Aurora Pay (fintech fictícia).

Cada função `detectar_rXX` implementa uma regra para um risco da matriz
(01-mapeamento-lgpd/matriz_risco.csv, coluna "evidencia_esperada_nos_logs_fase2")
e devolve uma lista de alertas no formato:

    risco, usuario_ou_origem, inicio, evidencia, severidade

Princípio geral: os limites NÃO são números "chutados". Sempre que possível,
eles são calculados a partir do comportamento normal observado nos próprios
dados (percentis, distribuições, taxas de base) e a justificativa está ao lado
de cada constante.

Observação: o arquivo dados/GABARITO_incidentes_plantados.csv NÃO é lido aqui.
A coluna transacoes.fraude_flag também NÃO é usada para detectar (seria "colar
a resposta"); ela só pode servir depois, para conferir o resultado.

Como rodar (a partir da raiz do projeto ou desta pasta):
    python 02-analise-logs/detectar_anomalias.py
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
PASTA_SCRIPT = Path(__file__).resolve().parent
RAIZ = PASTA_SCRIPT.parent
DADOS = RAIZ / "dados"
SAIDA = PASTA_SCRIPT / "alertas_detectados.csv"

COLUNAS_SAIDA = ["risco", "usuario_ou_origem", "inicio", "evidencia", "severidade"]

# Rede interna da empresa: todos os acessos normais de funcionários vêm de
# 10.20.x.x (faixa privada RFC 1918). Qualquer outro IP é tratado como externo.
PREFIXO_REDE_INTERNA = "10.20."

NIVEIS = ["Baixo", "Médio", "Alto", "Crítico"]


def subir_nivel(nivel: str, passos: int = 1) -> str:
    """Aumenta a severidade em `passos` níveis, sem passar de 'Crítico'."""
    i = min(NIVEIS.index(nivel) + passos, len(NIVEIS) - 1)
    return NIVEIS[i]


def ip_externo(serie: pd.Series) -> pd.Series:
    return ~serie.fillna("").str.startswith(PREFIXO_REDE_INTERNA)


# ---------------------------------------------------------------------------
# Leitura e qualidade dos dados
# ---------------------------------------------------------------------------
def carregar_dados() -> dict[str, pd.DataFrame]:
    logs = pd.read_csv(DADOS / "logs_acesso.csv")
    logs["timestamp"] = pd.to_datetime(logs["timestamp"], errors="coerce")

    trans = pd.read_csv(DADOS / "transacoes.csv")
    # As datas de transações têm nanossegundos; ISO8601 lê os dois formatos.
    trans["data_hora"] = pd.to_datetime(trans["data_hora"], format="ISO8601", errors="coerce")

    func = pd.read_csv(DADOS / "funcionarios.csv")
    func["data_desligamento"] = pd.to_datetime(func["data_desligamento"], errors="coerce")

    cli = pd.read_csv(DADOS / "clientes.csv")
    matriz = pd.read_csv(RAIZ / "01-mapeamento-lgpd" / "matriz_risco.csv")

    return {"logs": logs, "trans": trans, "func": func, "cli": cli, "matriz": matriz}


def checar_qualidade(d: dict[str, pd.DataFrame]) -> None:
    """Imprime um diagnóstico simples: linhas, nulos, duplicados, datas."""
    print("=== Qualidade dos dados ===")
    for nome in ["logs", "trans", "func", "cli"]:
        df = d[nome]
        nulos = df.isna().sum()
        nulos = nulos[nulos > 0].to_dict()
        print(
            f"- {nome}: {len(df)} linhas | duplicadas: {df.duplicated().sum()} "
            f"| ids repetidos: {df.iloc[:, 0].duplicated().sum()} | nulos: {nulos or 'nenhum'}"
        )
    for nome, col in [("logs", "timestamp"), ("trans", "data_hora")]:
        s = d[nome][col]
        print(f"- {nome}.{col}: {s.isna().sum()} datas inválidas | {s.min()} até {s.max()}")
    print()


def horario_comercial(logs: pd.DataFrame) -> tuple[int, int]:
    """
    Descobre o horário de expediente a partir dos dados: as horas em que
    ocorre pelo menos 0,5% dos eventos de funcionários vindos da rede interna
    (horas "vazias" ou quase vazias ficam de fora). Resultado aqui: 8h às 19h59.
    """
    internos = logs[logs["usuario"].str.match(r"^u\d+$") & ~ip_externo(logs["ip_origem"])]
    por_hora = internos["timestamp"].dt.hour.value_counts(normalize=True).sort_values(ascending=False)
    horas = por_hora[por_hora >= 0.005].index
    return int(horas.min()), int(horas.max())


def fora_do_expediente(ts: pd.Series, expediente: tuple[int, int]) -> pd.Series:
    h = ts.dt.hour
    fim_de_semana = ts.dt.day_of_week >= 5
    return (h < expediente[0]) | (h > expediente[1]) | fim_de_semana


def poisson_cauda(k: int, lam: float) -> float:
    """P(X >= k) para X ~ Poisson(lam). Usado para medir 'quão raro' é um evento."""
    if k <= 0:
        return 1.0
    acumulado = sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(k))
    return max(0.0, 1.0 - acumulado)


# ---------------------------------------------------------------------------
# R01 - Acesso indevido por funcionário a dados de clientes
# ---------------------------------------------------------------------------
# Evidência esperada: consultas de um usuário a clientes sem relação com sua rotina.
#
# Regra: clientes VIP são 2% da base. Se um funcionário atende clientes "ao acaso"
# (fila de atendimento), esperamos que ~2% das suas consultas do dia sejam VIP.
# Para cada funcionário e dia, comparamos quantos VIPs DIFERENTES ele consultou
# com o esperado pela distribuição de Poisson (lambda = consultas_do_dia * 2%).
# Se a chance de isso acontecer por acaso for menor que 1 em 1.000 (p < 0,001),
# o dia é marcado. Exigimos também pelo menos 2 dias marcados, para separar um
# padrão repetido de um dia azarado.
R01_P_LIMITE = 0.001
R01_MIN_DIAS = 2


def detectar_r01(d, expediente) -> list[dict]:
    logs, cli, func = d["logs"], d["cli"], d["func"]
    vips = set(cli.loc[cli["vip"], "cliente_id"])
    taxa_base = len(vips) / len(cli)

    consultas = logs[logs["cliente_id"].notna() & logs["usuario"].isin(func["usuario"])].copy()
    consultas["dia"] = consultas["timestamp"].dt.date
    consultas["eh_vip"] = consultas["cliente_id"].isin(vips)

    por_dia = consultas.groupby(["usuario", "dia"]).agg(
        total=("cliente_id", "size"),
        vips_distintos=("cliente_id", lambda s: s[consultas.loc[s.index, "eh_vip"]].nunique()),
    ).reset_index()
    por_dia["esperado"] = por_dia["total"] * taxa_base
    por_dia["p"] = [poisson_cauda(k, lam) for k, lam in zip(por_dia["vips_distintos"], por_dia["esperado"])]
    marcados = por_dia[por_dia["p"] < R01_P_LIMITE]

    alertas = []
    setor = func.set_index("usuario")["setor"]
    for usuario, g in marcados.groupby("usuario"):
        if len(g) < R01_MIN_DIAS:
            continue
        g = g.sort_values("dia")
        total_vip = consultas[(consultas["usuario"] == usuario) & consultas["eh_vip"]]
        pct = len(total_vip) / (consultas["usuario"] == usuario).sum()
        alertas.append({
            "risco": "R01",
            "usuario_ou_origem": usuario,
            "inicio": total_vip["timestamp"][total_vip["timestamp"].dt.date == g["dia"].iloc[0]].min(),
            "evidencia": (
                f"{len(g)} dias com consultas concentradas em clientes VIP "
                f"({int(g['vips_distintos'].sum())} VIPs distintos nesses dias, "
                f"esperado ~{g['esperado'].sum():.1f}; menor p={g['p'].min():.1e}). "
                f"VIP = {pct:.1%} das consultas do usuário vs {taxa_base:.0%} da base. "
                f"Setor: {setor.get(usuario, '?')}. Dias: {', '.join(str(x) for x in g['dia'])}"
            ),
            "severidade": "Alto" if len(g) < 5 else "Crítico",
        })
    return alertas


# ---------------------------------------------------------------------------
# R02 - Exfiltração em massa por exportação
# ---------------------------------------------------------------------------
# Evidência esperada: exportações grandes fora do horário ou de IP externo.
#
# Regra: "grande" = acima da cerca de outlier extremo de Tukey (Q3 + 3*IQR)
# calculada sobre todas as exportações do DWH. Isso é um critério estatístico
# clássico e não depende de escolher um número na mão.
# Alerta se: volume grande E (fora do expediente OU IP externo).
# Exportações seguidas do mesmo usuário (intervalo < 1h) viram um único episódio.
R02_JANELA_EPISODIO = pd.Timedelta("1h")


def detectar_r02(d, expediente) -> list[dict]:
    logs = d["logs"]
    exp = logs[logs["acao"] == "exportacao"].copy()
    q1, q3 = exp["qtd_registros"].quantile([0.25, 0.75])
    limite = q3 + 3 * (q3 - q1)

    exp["grande"] = exp["qtd_registros"] > limite
    exp["fora_hora"] = fora_do_expediente(exp["timestamp"], expediente)
    exp["externo"] = ip_externo(exp["ip_origem"])
    susp = exp[exp["grande"] & (exp["fora_hora"] | exp["externo"])].sort_values(["usuario", "timestamp"])

    alertas = []
    for usuario, g in susp.groupby("usuario"):
        episodio = (g["timestamp"].diff() > R02_JANELA_EPISODIO).cumsum()
        for _, e in g.groupby(episodio):
            fatores = []
            if e["fora_hora"].any():
                fatores.append("fora do expediente/fim de semana")
            if e["externo"].any():
                fatores.append(f"IP externo {', '.join(e['ip_origem'].unique())}")
            sev = "Crítico" if len(fatores) == 2 else "Alto"
            alertas.append({
                "risco": "R02",
                "usuario_ou_origem": usuario,
                "inicio": e["timestamp"].min(),
                "evidencia": (
                    f"{len(e)} exportações do DWH somando {int(e['qtd_registros'].sum())} registros "
                    f"(cada uma > limite {limite:.0f}; mediana normal {exp['qtd_registros'].median():.0f}); "
                    + "; ".join(fatores)
                ),
                "severidade": sev,
            })
    return alertas


# ---------------------------------------------------------------------------
# R03 - Credential stuffing na API
# ---------------------------------------------------------------------------
# Evidência esperada: pico de falhas de login seguido de sucessos a partir de poucos IPs.
#
# Regra: no SSO, o funcionário que MAIS errou a senha errou 4 vezes nos 3 meses
# inteiros. Usamos 5x esse máximo, concentrado em apenas 1 hora, como limite
# para um IP: algo muito acima de qualquer erro humano.
# Alerta se um IP externo passa do limite numa janela de 1h E depois consegue
# login_ok (sinal de que alguma credencial vazada funcionou).
R03_JANELA = "1h"
R03_FATOR = 5


def detectar_r03(d, expediente) -> list[dict]:
    logs = d["logs"]
    sso_falhas = logs[(logs["sistema"] == "sso") & (logs["acao"] == "login_falha")]
    max_humano = int(sso_falhas.groupby("usuario").size().max())
    limite = R03_FATOR * max(max_humano, 1)

    logins = logs[logs["acao"].isin(["login_falha", "login_ok"]) & ip_externo(logs["ip_origem"])].copy()
    logins["falha"] = (logins["acao"] == "login_falha").astype(int)

    ips_suspeitos = []
    for ip, g in logins.groupby("ip_origem"):
        g = g.set_index("timestamp").sort_index()
        pico = g["falha"].rolling(R03_JANELA).sum().max()
        if pico < limite:
            continue
        primeira_falha = g.index[g["falha"] == 1].min()
        sucessos = g[(g["falha"] == 0) & (g.index > primeira_falha)]
        ips_suspeitos.append({
            "ip": ip, "inicio": g.index.min(), "fim": g.index.max(),
            "falhas": int(g["falha"].sum()), "sucessos": len(sucessos), "pico": int(pico),
            "alvo": ", ".join(g["usuario"].unique()),
        })

    # IPs atacando ao mesmo tempo = mesma campanha -> um único alerta.
    alertas = []
    if not ips_suspeitos:
        return alertas
    df = pd.DataFrame(ips_suspeitos).sort_values("inicio")
    campanha = (df["inicio"] > df["fim"].cummax().shift()).cumsum()
    for _, c in df.groupby(campanha):
        sucessos = int(c["sucessos"].sum())
        alertas.append({
            "risco": "R03",
            "usuario_ou_origem": f"{c['alvo'].iloc[0]} via {len(c)} IP(s): {', '.join(c['ip'])}",
            "inicio": c["inicio"].min(),
            "evidencia": (
                f"{int(c['falhas'].sum())} falhas de login entre {c['inicio'].min():%Y-%m-%d %H:%M} e "
                f"{c['fim'].max():%H:%M} (pico de {int(c['pico'].max())}/h por IP; limite {limite}/h = "
                f"{R03_FATOR}x o máximo de {max_humano} falhas de um funcionário no período todo); "
                f"{sucessos} logins bem-sucedidos depois das falhas"
            ),
            "severidade": "Crítico" if sucessos > 0 else "Alto",
        })
    return alertas


# ---------------------------------------------------------------------------
# R04 - Abuso de API por parceiro
# ---------------------------------------------------------------------------
# Evidência esperada: consultas sequenciais e regulares muito acima da média.
#
# Há só um parceiro nos logs, então não dá para comparar com "outros parceiros".
# Usamos duas referências internas:
#  (a) Volume: consultas a clientes por hora acima do percentil 99 de TODOS os
#      pares usuário-hora de funcionários (o que um humano faz no pior caso).
#  (b) Regularidade: coeficiente de variação (desvio/média) dos intervalos entre
#      requisições < 0,1. Pessoas têm intervalos irregulares (CV ~1); um script
#      que varre a base tem intervalos quase constantes (CV ~0).
R04_CV_MAX = 0.1


def detectar_r04(d, expediente) -> list[dict]:
    logs, func = d["logs"], d["func"]
    consultas = logs[logs["acao"] == "consulta_cliente"].copy()
    consultas["hora"] = consultas["timestamp"].dt.floor("h")

    humanos = consultas[consultas["usuario"].isin(func["usuario"])]
    p99_hora = humanos.groupby(["usuario", "hora"]).size().quantile(0.99)

    externos = consultas[~consultas["usuario"].isin(func["usuario"])]
    alertas = []
    for (origem, dia), g in externos.groupby(["usuario", externos["timestamp"].dt.date]):
        g = g.sort_values("timestamp")
        por_hora = g.groupby("hora").size()
        intervalos = g["timestamp"].diff().dt.total_seconds().dropna()
        if len(intervalos) < 10:
            continue
        cv = intervalos.std() / intervalos.mean() if intervalos.mean() > 0 else 0
        if por_hora.max() > p99_hora and cv < R04_CV_MAX:
            alertas.append({
                "risco": "R04",
                "usuario_ou_origem": f"{origem} ({', '.join(g['ip_origem'].unique())})",
                "inicio": g["timestamp"].min(),
                "evidencia": (
                    f"{len(g)} consultas a {g['cliente_id'].nunique()} clientes distintos em "
                    f"{(g['timestamp'].max() - g['timestamp'].min()).total_seconds() / 3600:.1f}h; "
                    f"pico {por_hora.max()}/h vs p99 humano {p99_hora:.0f}/h; "
                    f"intervalo médio {intervalos.mean():.0f}s com CV={cv:.2f} (automatizado)"
                ),
                "severidade": "Alto",
            })
    return alertas


# ---------------------------------------------------------------------------
# R05 - Conta de ex-funcionário ainda ativa
# ---------------------------------------------------------------------------
# Evidência esperada: acessos de usuário com data_desligamento já passada.
#
# Regra objetiva: qualquer evento cuja DATA seja posterior à data de desligamento.
# O próprio dia do desligamento é tolerado (a pessoa ainda pode estar trabalhando
# até o fim do expediente). A severidade sobe se houver IP externo ou horário atípico.
def detectar_r05(d, expediente) -> list[dict]:
    logs, func = d["logs"], d["func"]
    deslig = func.dropna(subset=["data_desligamento"]).set_index("usuario")["data_desligamento"]

    alertas = []
    for usuario, data in deslig.items():
        apos = logs[(logs["usuario"] == usuario) & (logs["timestamp"].dt.normalize() > data)]
        if apos.empty:
            continue
        dias = sorted(apos["timestamp"].dt.date.unique())
        externo = ip_externo(apos["ip_origem"]).any()
        fora = fora_do_expediente(apos["timestamp"], expediente).any()
        sev = "Médio"
        if externo or fora:
            sev = subir_nivel(sev)
        if externo and fora:
            sev = subir_nivel(sev)
        alertas.append({
            "risco": "R05",
            "usuario_ou_origem": usuario,
            "inicio": apos["timestamp"].min(),
            "evidencia": (
                f"Desligado(a) em {data:%Y-%m-%d}, mas fez {len(apos)} acessos em {len(dias)} dia(s) "
                f"depois ({', '.join(str(x) for x in dias)}); "
                f"{apos['cliente_id'].nunique()} clientes consultados; "
                f"IPs: {', '.join(apos['ip_origem'].unique())}"
                + ("; fora do expediente" if fora else "")
            ),
            "severidade": sev,
        })
    return alertas


# ---------------------------------------------------------------------------
# R06 - Tomada de conta de clientes (account takeover)
# ---------------------------------------------------------------------------
# Evidência esperada: novo dispositivo seguido de sequência de Pix em poucos minutos.
#
# Regra:
#  - "Dispositivo novo" = dispositivo que aparece pela primeira vez DEPOIS do
#    primeiro dispositivo já usado pelo cliente.
#  - Nos 30 min após a primeira aparição, contamos Pix feitos nesse dispositivo.
#  - Limite de 3 Pix: nos dados, o intervalo entre dois Pix do mesmo cliente
#    fica abaixo de ~2,4h em só 1% dos casos; 3 Pix em 30 min é raríssimo.
#  - Valor: soma > 10x o maior valor já movimentado pelo cliente antes.
# Alerta se as três condições ocorrem juntas.
R06_JANELA = pd.Timedelta("30min")
R06_MIN_PIX = 3
R06_FATOR_VALOR = 10


def detectar_r06(d, expediente) -> list[dict]:
    t = d["trans"].sort_values("data_hora")
    primeira_vez = t.groupby(["cliente_id", "dispositivo_id"])["data_hora"].min().reset_index()
    primeira_vez["ordem"] = primeira_vez.groupby("cliente_id")["data_hora"].rank(method="first")
    novos = primeira_vez[primeira_vez["ordem"] > 1]

    alertas = []
    for _, n in novos.iterrows():
        tc = t[t["cliente_id"] == n["cliente_id"]]
        antes = tc[tc["data_hora"] < n["data_hora"]]
        janela = tc[
            (tc["dispositivo_id"] == n["dispositivo_id"])
            & (tc["data_hora"] >= n["data_hora"])
            & (tc["data_hora"] <= n["data_hora"] + R06_JANELA)
            & (tc["tipo"] == "pix")
        ]
        if len(janela) < R06_MIN_PIX or antes.empty:
            continue
        maior_antes = antes["valor"].max()
        if janela["valor"].sum() <= R06_FATOR_VALOR * maior_antes:
            continue
        duracao = (janela["data_hora"].max() - janela["data_hora"].min()).total_seconds() / 60
        alertas.append({
            "risco": "R06",
            "usuario_ou_origem": f"{n['cliente_id']} (disp. {n['dispositivo_id']}, IP {janela['ip'].iloc[0]})",
            "inicio": n["data_hora"],
            "evidencia": (
                f"Dispositivo nunca visto + {len(janela)} Pix em {duracao:.0f} min somando "
                f"R$ {janela['valor'].sum():,.2f} (maior valor anterior do cliente: R$ {maior_antes:,.2f}; "
                f"mediana anterior R$ {antes['valor'].median():,.2f})"
                + ("; madrugada/fora do expediente" if fora_do_expediente(janela["data_hora"], expediente).any() else "")
            ),
            "severidade": "Crítico",
        })
    return alertas


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
DETECTORES = [detectar_r01, detectar_r02, detectar_r03, detectar_r04, detectar_r05, detectar_r06]


def main() -> pd.DataFrame:
    d = carregar_dados()
    checar_qualidade(d)
    expediente = horario_comercial(d["logs"])
    print(f"Expediente inferido dos dados: {expediente[0]}h às {expediente[1]}h59 (seg-sex)\n")

    alertas = []
    for detector in DETECTORES:
        achados = detector(d, expediente)
        print(f"{detector.__name__}: {len(achados)} alerta(s)")
        alertas.extend(achados)

    df = pd.DataFrame(alertas, columns=COLUNAS_SAIDA)
    df["inicio"] = pd.to_datetime(df["inicio"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.sort_values(["risco", "inicio"]).reset_index(drop=True)
    df.to_csv(SAIDA, index=False, encoding="utf-8")
    print(f"\n{len(df)} alertas salvos em {SAIDA.relative_to(RAIZ)}")
    return df


if __name__ == "__main__":
    main()
