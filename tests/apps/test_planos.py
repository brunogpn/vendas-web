"""Produto → planos → entregáveis (migration 085): o checkout vende um plano; o pedido grava os itens dele."""
from decimal import Decimal

import pytest

import database

BASICO = {'id': 8, 'produto_id': 12, 'slug': 'basico', 'nome': 'Fatias que Vendem', 'padrao': 1, 'ativo': 1,
          'preco_promocional': Decimal('10.00'), 'desconto_oferta': Decimal('0.00')}
COMPLETO = {'id': 30, 'produto_id': 12, 'slug': 'completo', 'nome': 'Fatias que Vendem — Completo', 'padrao': 0,
            'ativo': 1, 'preco_promocional': Decimal('22.00'), 'desconto_oferta': Decimal('7.00')}


def item(id, papel, tipo='ebook', nome='Fatias que Vendem', preco='0.00', dias=None, plano_id=30):
    return {'id': id, 'produto_id': 12, 'plano_id': plano_id, 'entregavel_id': id + 100, 'papel': papel, 'ordem': 1,
            'dias': dias, 'preco_original': Decimal(preco), 'preco_promocional': Decimal(preco), 'tipo': tipo,
            'app_slug': 'fatia' if tipo == 'app' else None, 'nome_venda': nome, 'descricao': None,
            'path_arquivo': None if tipo == 'app' else f'{nome}.pdf', 'nome_arquivo': None if tipo == 'app' else f'{nome}.pdf',
            'imagem_grande': None, 'imagem_pequena': None}


ITENS_COMPLETO = [item(1, 'principal', 'app', 'App Fatias', dias=90), item(2, 'principal'),
                  item(3, 'bonus', nome='Bolos Caseiros'), item(4, 'bump', nome='Brigadeiros', preco='6.90')]


class Banco:
    """Responde às consultas de planos/itens a partir de listas em memória e guarda o que foi gravado."""
    def __init__(self, planos, itens):
        self.planos, self.itens, self.gravados, self.sqls = planos, itens, [], []

    def execute_query(self, sql, params=None, **kw):
        self.sqls.append((sql, params))
        if 'FROM produto_planos WHERE produto_id = %s AND slug = %s' in sql:
            return next((p for p in self.planos if p['produto_id'] == params[0] and p['slug'] == params[1]
                         and p['ativo']), None)
        if 'FROM produto_planos WHERE produto_id = %s AND padrao = 1' in sql:
            return next((p for p in self.planos if p['produto_id'] == params[0] and p['padrao'] and p['ativo']), None)
        if 'FROM plano_entregaveis pe JOIN entregaveis' in sql:
            linhas = [i for i in self.itens if i['plano_id'] == params[0]]
            if "pe.papel = 'bump' AND pe.id IN" in sql:
                return [i for i in linhas if i['papel'] == 'bump' and i['id'] in params[1:]]
            if len(params) > 1:
                linhas = [i for i in linhas if i['papel'] == params[1]]
            return linhas
        return None

    def execute_many(self, sql, lista):
        self.gravados.extend(lista)


@pytest.fixture
def banco(monkeypatch):
    b = Banco([dict(BASICO), dict(COMPLETO)],
              [item(10, 'principal', plano_id=8), item(11, 'bonus', nome='Bolos Caseiros', plano_id=8),
               item(12, 'bump', nome='Brigadeiros', preco='6.90', plano_id=8)] + ITENS_COMPLETO)
    monkeypatch.setattr(database, 'db', b)
    return b


def test_sem_plano_na_url_vende_o_padrao(banco):
    plano = database.get_plano_venda(12)
    assert plano['slug'] == 'basico' and plano['app_slug'] is None
    assert [p['nome_venda'] for p in plano['principais']] == ['Fatias que Vendem']


def test_plano_pelo_slug_traz_os_principais_e_o_app(banco):
    plano = database.get_plano_venda(12, 'completo')
    assert plano['app_slug'] == 'fatia'
    assert [p['tipo'] for p in plano['principais']] == ['app', 'ebook']
    assert database.resolver_plano_checkout(12, 'completo')[1] == 22.0


@pytest.mark.parametrize('slug', ['nao-existe', 'inativo', 'vazio'])
def test_plano_que_nao_esta_a_venda_e_recusado(banco, slug):
    banco.planos += [{**COMPLETO, 'id': 40, 'slug': 'inativo', 'ativo': 0},
                     {**COMPLETO, 'id': 41, 'slug': 'vazio'}]   # sem item principal
    assert database.get_plano_venda(12, slug) is None
    assert database.resolver_plano_checkout(12, slug) == (None, None)


def test_produto_sem_plano_continua_recusado(banco):
    assert database.get_plano_venda(99) is None


def test_override_de_teste_so_troca_o_valor(banco, monkeypatch):
    monkeypatch.setenv('CHECKOUT_VALOR_TESTE_PRODUTO_12', '1.00')
    plano, valor = database.resolver_plano_checkout(12, 'completo')
    assert plano['slug'] == 'completo' and valor == 1.0


def test_bump_de_outro_plano_e_ignorado(banco):
    completo = database.get_plano_venda(12, 'completo')
    assert [b['id'] for b in database.listar_bumps_validos(completo, [4, 12, 'x', None])] == [4]
    assert database.listar_bumps_validos(completo, []) == []


def test_checkout_le_os_itens_do_plano_uma_vez_so(banco):
    plano = database.get_plano_venda(12, 'completo')
    consultas = [q for q, _ in banco.sqls if 'FROM plano_entregaveis' in q]
    assert len(consultas) == 1
    assert [i['id'] for i in database.itens_do_plano(plano, 'bonus')] == [3]


@pytest.mark.parametrize('kwargs,esperado', [
    ({}, '/pay/12'),
    ({'plano': BASICO}, '/pay/12'),                                         # padrão: sem ?plano=
    ({'plano': COMPLETO}, '/pay/12?plano=completo'),
    ({'plano': COMPLETO, 'pedido': 9, 'oferta': 'T.1'}, '/pay/12?pedido=9&plano=completo&oferta=T.1'),
    ({'plano': COMPLETO, 'v2': True, 'ref': 'a b'}, '/pay2/12?ref=a+b&plano=completo'),
])
def test_link_checkout(kwargs, esperado):
    from web.links import link_checkout
    assert link_checkout(12, **kwargs) == esperado


def test_itens_do_pedido_com_varios_principais(banco):
    """Completo = app + e-book: o preço do plano fica no primeiro principal, os outros e o bônus valem 0;
    o bump leva o preço dele; o item app grava app_slug (é por ele que a licença é liberada)."""
    plano = database.get_plano_venda(12, 'completo')
    bumps = database.listar_bumps_validos(plano, [4])
    database.criar_itens_pedido_web(500, plano, 15.0, bumps)
    gravados = [(g[1], g[2], g[3], g[5], float(g[8])) for g in banco.gravados]
    assert gravados == [('principal', 1, 'fatia', 'App Fatias', 15.0),
                        ('principal', 2, None, 'Fatias que Vendem', 0.0),
                        ('bonus', 3, None, 'Bolos Caseiros', 0.0),
                        ('bump', 4, None, 'Brigadeiros', 6.9)]
    assert ('UPDATE pedidos SET plano_id = %s WHERE id = %s', (30, 500)) in banco.sqls


def test_itens_do_whatsapp_sao_os_do_plano_padrao(banco):
    database.criar_itens_pedido_web(501, database.get_plano_venda(12), 0.0)
    assert [(g[1], g[5]) for g in banco.gravados] == [('principal', 'Fatias que Vendem'), ('bonus', 'Bolos Caseiros')]


def test_itens_de_musica_gravam_o_recurso(monkeypatch):
    """Plano da Música: a música (principal) e o QR code (bump) gravam o recurso — é por ele que a música é
    liberada; e-book e app não gravam recurso."""
    plano = {'id': 40, 'produto_id': 20, 'slug': 'musica', 'nome': 'Música', 'padrao': 1, 'ativo': 1,
             'preco_promocional': Decimal('29.90'), 'desconto_oferta': Decimal('0.00')}
    musica = dict(item(20, 'principal', 'musica', 'Sua música', plano_id=40), recurso='musica',
                  path_arquivo=None, nome_arquivo=None)
    qr = dict(item(21, 'bump', 'musica', 'Cartão com QR code', preco='9.90', plano_id=40), recurso='qrcode',
              path_arquivo=None, nome_arquivo=None)
    b = Banco([plano], [musica, qr])
    monkeypatch.setattr(database, 'db', b)
    p = database.get_plano_venda(20, 'musica')
    database.criar_itens_pedido_web(600, p, 29.9, database.listar_bumps_validos(p, [21]))
    assert [(g[1], g[3], g[4], float(g[8])) for g in b.gravados] == [('principal', None, 'musica', 29.9),
                                                                     ('bump', None, 'qrcode', 9.9)]


def test_sem_plano_nao_grava_itens(banco):
    database.criar_itens_pedido_web(502, None, 10.0)
    assert banco.gravados == [] and banco.sqls == []


@pytest.mark.parametrize('pedido,plano,esperado', [
    ({'estado_id': 1003, 'plano_id': None}, COMPLETO, True),   # rascunho: ainda sem plano
    ({'estado_id': 1006, 'plano_id': 30}, COMPLETO, True),
    ({'estado_id': 1006, 'plano_id': 8}, COMPLETO, False),     # cartão negado do Básico: não reaproveita no Completo
    ({'estado_id': 1007, 'plano_id': None}, BASICO, True),     # de antes dos planos = padrão
    ({'estado_id': 1007, 'plano_id': None}, COMPLETO, False),
])
def test_pedido_do_plano(pedido, plano, esperado):
    import importlib
    checkout = importlib.import_module('web.checkout')  # 'from web import checkout' pega a rota
    assert checkout.pedido_do_plano(pedido, plano) is esperado


def test_estante_nao_lista_o_app_como_livro(monkeypatch):
    import importlib
    checkout = importlib.import_module('web.checkout')
    itens = [{'id': 1, 'tipo': 'principal', 'entregavel_id': 18, 'path_arquivo': None, 'nome': 'App'},
             {'id': 2, 'tipo': 'bonus', 'entregavel_id': 7, 'path_arquivo': 'f.pdf', 'nome': 'Fatias que Vendem'}]
    monkeypatch.setattr(database, 'listar_itens_pedido_ebook', lambda pid: itens)
    monkeypatch.setattr(database, 'listar_pedidos_pagos_relacionados', lambda *a: [])
    monkeypatch.setattr(database, 'listar_pedidos_vinculados_pagos', lambda pid: [])
    r = checkout.listar_itens_ebook_do_cliente({'id': 1, 'guid': 'g', 'estado_id': 1000, 'email': 'a@b', 'contact_phone': None})
    assert [i['nome'] for i in r] == ['Fatias que Vendem']


def test_cross_sell_de_ebook_pula_o_que_ela_tem_e_planos_com_app(monkeypatch):
    """Também fica fora a Música: a compra dela começa no quiz de /musica, não no checkout."""
    linhas = [{'produto_id': 12, 'principais': '5', 'tem_app': 0, 'tem_musica': 0, 'nome_venda': 'Fatias'},
              {'produto_id': 14, 'principais': '6', 'tem_app': 0, 'tem_musica': 0, 'nome_venda': 'Orquídeas'},
              {'produto_id': 16, 'principais': '18', 'tem_app': 1, 'tem_musica': 0, 'nome_venda': 'App'},
              {'produto_id': 20, 'principais': '30', 'tem_app': 0, 'tem_musica': 1, 'nome_venda': 'Música'}]
    monkeypatch.setattr(database.db, 'execute_query', lambda *a, **k: linhas)
    assert [c['produto_id'] for c in database.listar_produtos_cross_sell_cliente({5})] == [14]


def test_app_em_piloto_nao_e_oferecido_na_estante(monkeypatch):
    """publico=False (piloto): quem não tem o app não o vê no cross-sell; quem tem vê em "Meus apps"."""
    import dataclasses
    import apps
    from apps._nucleo import estante, licenca as lic
    plano = {**COMPLETO, 'app_slug': 'fatia', 'dias': 90, 'vitrine': 1, 'renovacao': 0, 'produto_ativo': 1,
             'disponivel_web': 1, 'imagem_pequena': None, 'imagem_grande': None}
    renovacao = {**plano, 'id': 31, 'slug': 'renovacao', 'vitrine': 0, 'renovacao': 1}
    monkeypatch.setattr(database, 'listar_planos_com_app', lambda *a, **k: [plano, renovacao])
    monkeypatch.setattr(lic, 'buscar_cliente_por_email', lambda e: None)  # cliente sem app
    for publico, esperado in ((False, []), (True, [30])):
        cfg = dataclasses.replace(apps.APPS['fatia'], publico=publico)
        monkeypatch.setattr(estante, 'APPS', {'fatia': cfg})
        meus, ofertas = estante.apps_da_estante({'email': 'x@y.com'})
        assert meus == [] and [o['plano_id'] for o in ofertas] == esperado
    # Com oferta: preço com desconto e token deste plano no link.
    assert ofertas[0]['preco_promocional'] == 15.0 and ofertas[0]['oferta']


def test_estante_prefere_o_plano_com_app_do_produto_do_pedido(monkeypatch):
    from apps._nucleo import estante, licenca as lic
    base = {'app_slug': 'fatia', 'dias': 90, 'vitrine': 1, 'renovacao': 0, 'produto_ativo': 1, 'disponivel_web': 1,
            'imagem_pequena': None, 'imagem_grande': None, 'desconto_oferta': 0, 'padrao': 0, 'slug': 'completo',
            'nome': 'X', 'preco_promocional': Decimal('22.00')}
    planos = [{**base, 'id': 30, 'produto_id': 12}, {**base, 'id': 16, 'produto_id': 16, 'padrao': 1}]  # empate de preço
    monkeypatch.setattr(database, 'listar_planos_com_app', lambda *a, **k: planos)
    monkeypatch.setattr(lic, 'buscar_cliente_por_email', lambda e: None)
    assert [o['plano_id'] for o in estante.apps_da_estante({'email': 'x@y', 'produto_id': 12})[1]] == [30]
    assert [o['plano_id'] for o in estante.apps_da_estante({'email': 'x@y', 'produto_id': 14})[1]] == [16]  # o mais caro


def test_financeiro_filtra_por_plano(monkeypatch):
    """O plano filtra resumo e lista, como a origem; 'todos' traz tudo."""
    import datetime
    t = lambda valor, forma, plano: {'horario': datetime.datetime(2026, 10, 1), 'valor': Decimal(valor), 'forma': forma,
                                     'fluxo_inicial': 'web', 'plano_id': plano}
    linhas = [t('10.00', 'pix', 8), t('22.00', 'cartao', 30), t('15.00', 'pix', 30)]
    monkeypatch.setattr(database.db, 'execute_query',
                        lambda sql, *a, **k: {'id': 8} if 'padrao = 1' in sql and 'UNION' not in sql else linhas)
    todos = database.busca_financeiro_produto(12, None, None)
    assert todos['resumo']['total_valor'] == 25.0 and todos['resumo']['total_cartao'] == 22.0
    completo = database.busca_financeiro_produto(12, None, None, plano='30')
    assert completo['resumo']['total_valor'] == 15.0 and completo['resumo']['total_cartao'] == 22.0
    assert len(completo['transacoes_filtradas']) == 2
    assert len(completo['transacoes']) == 3   # a lista completa continua (contadores dos botões)
    assert len(completo['transacoes_plano']) == 2  # contadores de origem/forma: só o plano escolhido


@pytest.mark.parametrize('url,esperado', [
    ('/pay/16', '/pay/12?plano=completo'),
    ('/pay/16?pedido=123&oferta=T.1', '/pay/12?pedido=123&plano=completo&oferta=T.1'),
    ('/pay2/16?ref=abc', '/pay2/12?ref=abc&plano=completo'),
])
def test_link_de_produto_que_virou_plano_redireciona(monkeypatch, url, esperado):
    """Produto 16 (Guiado) virou o Completo do 12 (migration 087): links antigos levam ao plano, com o pedido."""
    import importlib
    from flask import Flask
    app = Flask(__name__)  # Flask mínimo só com o blueprint do site (o app inteiro carrega o .env do dev)
    app.register_blueprint(importlib.import_module('web').web_bp)
    monkeypatch.setattr(database, 'get_produto_disponivel_web', lambda pid: None)
    monkeypatch.setattr(database, 'get_redirecionamento_produto',
                        lambda pid: {'produto_destino_id': 12, 'plano_slug': 'completo', 'plano_padrao': 0} if pid == 16 else None)
    r = app.test_client().get(url)
    assert r.status_code == 302 and r.headers['Location'] == esperado
    assert app.test_client().get('/pay/99').status_code == 404   # sem redirecionamento: como antes
