import datetime

from apps.fatia import progresso as prog
from apps.fatia.conteudo import PASSOS, TOTAL_PASSOS

HOJE = datetime.date(2026, 10, 12)


def _perfil(**kw):
    p = {'preco_fatia': None, 'custo_fatia': None, 'meta_mensal': None, 'dias_venda': None}
    p.update(kw)
    return p


def _tarefas(ids, dia=HOJE):
    return [{'tarefa_id': i, 'concluida_em': dia} for i in ids]


def test_metas_padrao_quando_a_cliente_nao_preencheu():
    m = prog.metas(_perfil())
    assert m['preco'] == 18 and m['meta'] == 1000 and m['dias_por_semana'] == 2
    assert m['custo'] == 18 * 0.3 and m['custo_estimado'] is True
    assert m['fatias_mes'] == 80                       # ceil(1000 / 12.6)
    assert m['fatias_por_dia_de_venda'] == 10          # ceil(80 / (2 * 4.3))


def test_metas_com_custo_da_calculadora_e_lucro_minimo():
    m = prog.metas(_perfil(preco_fatia=10, custo_fatia=10, meta_mensal=100, dias_venda='sab'))
    assert m['custo_estimado'] is False
    assert m['lucro_por_fatia'] == 0.5                 # nunca menos que R$ 0,50 (evita divisão por zero)
    assert m['dias_por_semana'] == 1


def test_sequencia_conta_ate_ontem_e_guarda_a_maior():
    um = datetime.timedelta(days=1)
    ativos = {HOJE - um, HOJE - 2 * um, HOJE - 10 * um, HOJE - 11 * um, HOJE - 12 * um, HOJE - 13 * um}
    atual, maior = prog.sequencia(ativos, HOJE)
    assert atual == 2          # hoje ainda sem atividade: a sequência de ontem não zera
    assert maior == 4


def test_pontos_nivel_e_medalhas():
    feitas = [p['id'] for p in PASSOS[:6]]
    vendas = [{'data': HOJE, 'gasto': 50.0, 'fatias': 10, 'recebido': 180.0}]
    p = prog.calcular(_perfil(), _tarefas(feitas), vendas, HOJE)
    assert p['pontos'] == 6 * 10 + 5
    assert p['nivel']['nome'] == 'Confeiteira' and p['proximo_nivel']['nome'] == 'Feirante'
    ganhas = {m['id'] for m in p['medalhas'] if m['ganhou']}
    assert {'primeiro-passo', 'primeira-venda', 'lucro-100'} <= ganhas
    assert 'trilha' not in ganhas
    assert p['proximo_passo']['id'] == PASSOS[6]['id']
    assert p['total_mes']['lucro'] == 130
    assert p['falta_meta'] == 870


def test_fase_completa_e_trilha_inteira():
    todas = [x['id'] for x in PASSOS]
    p = prog.calcular(_perfil(), _tarefas(todas), [], HOJE)
    ganhas = {m['id'] for m in p['medalhas'] if m['ganhou']}
    assert {'fase-1', 'fase-5', 'trilha'} <= ganhas
    assert p['proximo_passo'] is None
    assert p['total_feitas'] == TOTAL_PASSOS


def test_conquistas_entre_antes_e_depois():
    antes = prog.calcular(_perfil(), [], [], HOJE)
    depois = prog.calcular(_perfil(), _tarefas([PASSOS[0]['id']]), [], HOJE)
    c = prog.conquistas(antes, depois)
    assert c['pontosGanhos'] == 10
    assert [m['id'] for m in c['novasMedalhas']] == ['primeiro-passo']
    assert c['subiuNivel'] is None
