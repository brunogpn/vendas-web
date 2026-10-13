"""SQL das tabelas do App Fatias (app_fatia_*, migration 081)."""
import json

from database import db
from apps._nucleo import datas

PERFIL_PADRAO = {'nome': None, 'meta_mensal': None, 'investimento': None, 'dias_venda': None,
                 'preco_fatia': None, 'custo_fatia': None, 'onboarding_ok': 0, 'som': 1}

_CAMPOS_PERFIL = ('nome', 'meta_mensal', 'investimento', 'dias_venda', 'preco_fatia', 'custo_fatia',
                  'onboarding_ok', 'som')


def _f(v):
    return None if v is None else float(v)


# ---------------------------------------------------------------- perfil

def perfil(cliente_id: int) -> dict:
    p = db.execute_query(
        "SELECT nome, meta_mensal, investimento, dias_venda, preco_fatia, custo_fatia, onboarding_ok, som "
        "FROM app_fatia_perfis WHERE cliente_id = %s", (cliente_id,), fetch_one=True)
    if not p:
        return dict(PERFIL_PADRAO)
    for k in ('meta_mensal', 'investimento', 'preco_fatia', 'custo_fatia'):
        p[k] = _f(p[k])
    p['onboarding_ok'] = int(p['onboarding_ok'] or 0)
    p['som'] = int(p['som'] if p['som'] is not None else 1)
    return p


def salvar_perfil(cliente_id: int, campos: dict) -> None:
    campos = {k: v for k, v in campos.items() if k in _CAMPOS_PERFIL}
    if not campos:
        return
    colunas = ', '.join(campos)
    marcas = ', '.join(['%s'] * len(campos))
    atualiza = ', '.join(f'{k} = VALUES({k})' for k in campos)
    db.execute_query(
        f"INSERT INTO app_fatia_perfis (cliente_id, {colunas}) VALUES (%s, {marcas}) "
        f"ON DUPLICATE KEY UPDATE {atualiza}",
        (cliente_id, *campos.values()))


# ---------------------------------------------------------------- trilha

def tarefas_concluidas(cliente_id: int) -> list[dict]:
    return db.execute_query(
        "SELECT tarefa_id, concluida_em FROM app_fatia_tarefas_concluidas WHERE cliente_id = %s",
        (cliente_id,), fetch_all=True) or []


def concluir_tarefa(cliente_id: int, tarefa_id: int) -> None:
    db.execute_query(
        "INSERT IGNORE INTO app_fatia_tarefas_concluidas (cliente_id, tarefa_id, concluida_em) VALUES (%s, %s, %s)",
        (cliente_id, tarefa_id, datas.hoje()))


def desfazer_tarefa(cliente_id: int, tarefa_id: int) -> None:
    db.execute_query("DELETE FROM app_fatia_tarefas_concluidas WHERE cliente_id = %s AND tarefa_id = %s",
                     (cliente_id, tarefa_id))


# ---------------------------------------------------------------- vendas

def lancamentos(cliente_id: int) -> list[dict]:
    """Registros de venda, do mais recente para o mais antigo."""
    linhas = db.execute_query(
        "SELECT data, gasto, fatias, recebido FROM app_fatia_lancamentos WHERE cliente_id = %s ORDER BY data DESC",
        (cliente_id,), fetch_all=True) or []
    return [{'data': l['data'], 'gasto': float(l['gasto']), 'fatias': int(l['fatias']),
             'recebido': float(l['recebido'])} for l in linhas]


def salvar_lancamento(cliente_id: int, data, gasto: float, fatias: int, recebido: float) -> None:
    db.execute_query(
        "INSERT INTO app_fatia_lancamentos (cliente_id, data, gasto, fatias, recebido) VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE gasto = VALUES(gasto), fatias = VALUES(fatias), recebido = VALUES(recebido)",
        (cliente_id, data, gasto, fatias, recebido))


def apagar_lancamento(cliente_id: int, data) -> None:
    db.execute_query("DELETE FROM app_fatia_lancamentos WHERE cliente_id = %s AND data = %s", (cliente_id, data))


# ---------------------------------------------------------------- preços

def mapa_precos(cliente_id: int) -> dict[str, dict]:
    linhas = db.execute_query(
        "SELECT item, preco, quantidade FROM app_fatia_precos WHERE cliente_id = %s",
        (cliente_id,), fetch_all=True) or []
    return {l['item']: {'preco': float(l['preco']), 'quantidade': float(l['quantidade'])} for l in linhas}


def salvar_preco(cliente_id: int, item: str, preco: float, quantidade: float) -> None:
    db.execute_query(
        "INSERT INTO app_fatia_precos (cliente_id, item, preco, quantidade) VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE preco = VALUES(preco), quantidade = VALUES(quantidade)",
        (cliente_id, item, preco, quantidade))


def apagar_preco(cliente_id: int, item: str) -> None:
    db.execute_query("DELETE FROM app_fatia_precos WHERE cliente_id = %s AND item = %s", (cliente_id, item))


# ---------------------------------------------------------------- lista de compras

def lista_compras(cliente_id: int) -> dict:
    linha = db.execute_query("SELECT dados FROM app_fatia_lista_compras WHERE cliente_id = %s",
                             (cliente_id,), fetch_one=True)
    if not linha:
        return {'receitas': {}, 'marcados': []}
    dados = linha['dados']
    if isinstance(dados, (bytes, bytearray)):
        dados = dados.decode()
    if isinstance(dados, str):
        dados = json.loads(dados)
    return {'receitas': dados.get('receitas') or {}, 'marcados': dados.get('marcados') or []}


def salvar_lista_compras(cliente_id: int, lista: dict) -> None:
    db.execute_query(
        "INSERT INTO app_fatia_lista_compras (cliente_id, dados) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE dados = VALUES(dados)",
        (cliente_id, json.dumps(lista, ensure_ascii=False)))
