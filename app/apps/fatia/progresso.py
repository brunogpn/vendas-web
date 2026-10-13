"""Pontos, níveis, medalhas, sequência e metas do App Fatias.

Nada disso fica gravado: tudo é calculado a partir das tarefas concluídas e das vendas lançadas
(porte do src/lib/progresso.ts do Bruno — mesmas constantes e regras).
"""
import datetime
import math

from apps._nucleo import datas
from apps.fatia import dados
from apps.fatia.conteudo import FASES, PASSOS, TOTAL_PASSOS

PONTOS_TAREFA = 10
PONTOS_DIA_LANCADO = 5
CUSTO_ESTIMADO = 0.3   # quando a cliente ainda não calculou o custo, estimamos 30% do preço
SEMANAS_NO_MES = 4.3
PRECO_PADRAO = 18
META_PADRAO = 1000

NIVEIS = [
    {'nome': 'Aprendiz', 'icone': 'Egg', 'min': 0},
    {'nome': 'Confeiteira', 'icone': 'ChefHat', 'min': 60},
    {'nome': 'Feirante', 'icone': 'Basket', 'min': 150},
    {'nome': 'Empreendedora', 'icone': 'Briefcase', 'min': 260},
    {'nome': 'Mestra das Fatias', 'icone': 'Crown', 'min': 400},
]

DIAS_SEMANA = [('seg', 'Seg'), ('ter', 'Ter'), ('qua', 'Qua'), ('qui', 'Qui'), ('sex', 'Sex'), ('sab', 'Sáb'), ('dom', 'Dom')]


def metas(perfil: dict) -> dict:
    preco = perfil.get('preco_fatia') or PRECO_PADRAO
    custo_gravado = perfil.get('custo_fatia')
    custo = custo_gravado if custo_gravado is not None else preco * CUSTO_ESTIMADO
    lucro_por_fatia = max(preco - custo, 0.5)
    meta = perfil.get('meta_mensal') or META_PADRAO
    dias = [d for d in (perfil.get('dias_venda') or '').split(',') if d]
    dias_por_semana = max(1, len(dias) or 2)
    fatias_mes = math.ceil(meta / lucro_por_fatia)
    return {
        'preco': preco, 'custo': custo, 'custo_estimado': custo_gravado is None,
        'lucro_por_fatia': lucro_por_fatia, 'meta': meta, 'dias_por_semana': dias_por_semana,
        'fatias_mes': fatias_mes,
        'fatias_por_dia_de_venda': math.ceil(fatias_mes / (dias_por_semana * SEMANAS_NO_MES)),
        'fatias_por_semana': math.ceil(fatias_mes / SEMANAS_NO_MES),
    }


def _totais(lista: list[dict]) -> dict:
    t = {'gasto': 0.0, 'recebido': 0.0, 'fatias': 0, 'lucro': 0.0}
    for l in lista:
        t['gasto'] += l['gasto']
        t['recebido'] += l['recebido']
        t['fatias'] += l['fatias']
        t['lucro'] += l['recebido'] - l['gasto']
    return t


def sequencia(dias_ativos: set, hoje: datetime.date) -> tuple[int, int]:
    """(atual, maior): dias seguidos com alguma atividade. A atual termina hoje ou ontem, para não
    "zerar" de manhã antes da cliente fazer algo."""
    um = datetime.timedelta(days=1)
    dia = hoje if hoje in dias_ativos else hoje - um
    atual = 0
    while dia in dias_ativos:
        atual += 1
        dia -= um
    maior = corrida = 0
    anterior = None
    for d in sorted(dias_ativos):
        corrida = corrida + 1 if anterior is not None and (d - anterior).days == 1 else 1
        maior = max(maior, corrida)
        anterior = d
    return atual, maior


def calcular(perfil: dict, tarefas: list[dict], vendas: list[dict], hoje: datetime.date | None = None) -> dict:
    """Progresso completo. `tarefas` = [{tarefa_id, concluida_em}], `vendas` = lançamentos (qualquer ordem)."""
    hoje = hoje or datas.hoje()
    feitas = {t['tarefa_id'] for t in tarefas}
    vendas = sorted(vendas, key=lambda l: datas.como_data(l['data']), reverse=True)
    mes = hoje.isoformat()[:7]
    do_mes = [l for l in vendas if datas.como_data(l['data']).isoformat().startswith(mes)]
    total_geral = _totais(vendas)
    total_mes = _totais(do_mes)
    de_hoje = next((l for l in vendas if datas.como_data(l['data']) == hoje), None)

    # Venda lançada com data antiga conta como atividade naquele dia.
    dias_ativos = {datas.como_data(t['concluida_em']) for t in tarefas} | {datas.como_data(l['data']) for l in vendas}
    seq_atual, seq_maior = sequencia(dias_ativos, hoje)

    pontos = len(feitas) * PONTOS_TAREFA + len(vendas) * PONTOS_DIA_LANCADO
    i_nivel = max(i for i, n in enumerate(NIVEIS) if pontos >= n['min'])
    nivel = NIVEIS[i_nivel]
    proximo_nivel = NIVEIS[i_nivel + 1] if i_nivel + 1 < len(NIVEIS) else None

    m = metas(perfil)
    proximo_passo = next((p for p in PASSOS if p['id'] not in feitas), None)

    def fase_completa(numero):
        return all(p['id'] in feitas for p in PASSOS if p['fase'] == numero)

    medalhas = [
        {'id': 'primeiro-passo', 'icone': 'Footprints', 'nome': 'Primeiro passo', 'descricao': 'Concluiu a primeira tarefa', 'ganhou': len(feitas) >= 1},
        *[{'id': f'fase-{f["numero"]}', 'icone': f['icone'], 'nome': f['medalha'],
           'descricao': f'Concluiu a fase "{f["nome"]}"', 'ganhou': fase_completa(f['numero'])} for f in FASES],
        {'id': 'primeira-venda', 'icone': 'Coins', 'nome': 'Primeira venda', 'descricao': 'Lançou a primeira venda', 'ganhou': total_geral['fatias'] > 0},
        {'id': '50-fatias', 'icone': 'Cake', 'nome': '50 fatias', 'descricao': 'Vendeu 50 fatias no total', 'ganhou': total_geral['fatias'] >= 50},
        {'id': '200-fatias', 'icone': 'Medal', 'nome': '200 fatias', 'descricao': 'Vendeu 200 fatias no total', 'ganhou': total_geral['fatias'] >= 200},
        {'id': 'lucro-100', 'icone': 'Money', 'nome': 'Primeiros R$ 100', 'descricao': 'Lucrou R$ 100 no total', 'ganhou': total_geral['lucro'] >= 100},
        {'id': 'lucro-1000', 'icone': 'Diamond', 'nome': 'Primeiros R$ 1.000', 'descricao': 'Lucrou R$ 1.000 no total', 'ganhou': total_geral['lucro'] >= 1000},
        {'id': 'sequencia-3', 'icone': 'Fire', 'nome': '3 dias seguidos', 'descricao': 'Usou o app 3 dias seguidos', 'ganhou': seq_maior >= 3},
        {'id': 'sequencia-7', 'icone': 'Lightning', 'nome': '7 dias seguidos', 'descricao': 'Usou o app 7 dias seguidos', 'ganhou': seq_maior >= 7},
        {'id': 'meta-mes', 'icone': 'Target', 'nome': 'Meta batida', 'descricao': 'Bateu a meta de lucro do mês', 'ganhou': total_mes['lucro'] >= m['meta']},
        {'id': 'trilha', 'icone': 'Trophy', 'nome': 'Trilha completa', 'descricao': f'Concluiu os {TOTAL_PASSOS} passos', 'ganhou': len(feitas) >= TOTAL_PASSOS},
    ]

    return {
        'feitas': feitas,
        'concluidas_em': {t['tarefa_id']: datas.como_data(t['concluida_em']) for t in tarefas},
        'total_feitas': len(feitas),
        'proximo_passo': proximo_passo,
        'vendas': vendas,
        'de_hoje': de_hoje,
        'total_mes': total_mes,
        'total_geral': total_geral,
        'sequencia': seq_atual,
        'pontos': pontos,
        'nivel': nivel,
        'proximo_nivel': proximo_nivel,
        'medalhas': medalhas,
        'medalhas_ganhas': sum(1 for x in medalhas if x['ganhou']),
        'metas': m,
        'falta_meta': max(m['meta'] - total_mes['lucro'], 0),
        'fatias_faltando': max(math.ceil((m['meta'] - total_mes['lucro']) / m['lucro_por_fatia']), 0),
    }


def progresso(cliente_id: int, perfil: dict | None = None) -> dict:
    return calcular(perfil if perfil is not None else dados.perfil(cliente_id),
                    dados.tarefas_concluidas(cliente_id), dados.lancamentos(cliente_id))


def conquistas(antes: dict, depois: dict) -> dict:
    """O que mudou entre dois momentos — alimenta a tela de comemoração."""
    ganhas_antes = {m['id'] for m in antes['medalhas'] if m['ganhou']}
    return {
        'pontosGanhos': depois['pontos'] - antes['pontos'],
        'pontos': depois['pontos'],
        'subiuNivel': depois['nivel'] if depois['nivel']['nome'] != antes['nivel']['nome'] else None,
        'novasMedalhas': [{'id': m['id'], 'icone': m['icone'], 'nome': m['nome']}
                          for m in depois['medalhas'] if m['ganhou'] and m['id'] not in ganhas_antes],
    }
