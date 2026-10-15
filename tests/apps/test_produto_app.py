"""Produto do tipo app (apps_produto, migration 082): o app vira o "principal" do checkout."""
from decimal import Decimal

import database

APP = {'produto_id': 16, 'app_slug': 'fatia', 'dias': 90, 'renovacao': 0, 'nome_venda': 'App Fatias — Plano Guiado',
       'descricao': 'Passo a passo', 'imagem_grande': 'app.webp', 'imagem_pequena': None,
       'preco_original': Decimal('49.90'), 'preco_promocional': Decimal('22.00')}


def test_produto_de_ebook_continua_igual(monkeypatch):
    ebook = {'id': 5, 'nome_venda': 'Fatias que Vendem', 'preco_promocional': Decimal('10.00'), 'path_arquivo': 'f.pdf'}
    monkeypatch.setattr(database.db, 'execute_query', lambda q, p=None, **k: ebook)
    chamadas = []
    monkeypatch.setattr(database, 'get_app_produto', lambda pid: chamadas.append(pid))
    assert database.get_ebook_principal_produto(12) is ebook
    assert chamadas == []  # nem consulta apps_produto quando há e-book principal


def test_produto_app_vira_o_principal(monkeypatch):
    monkeypatch.setattr(database.db, 'execute_query', lambda q, p=None, **k: None)
    monkeypatch.setattr(database, 'get_app_produto', lambda pid: APP)
    p = database.get_ebook_principal_produto(16)
    assert p['app_slug'] == 'fatia' and p['path_arquivo'] is None and p['id'] is None
    assert p['nome_venda'] == 'App Fatias — Plano Guiado' and p['preco_promocional'] == Decimal('22.00')
    principal, valor = database.resolver_valor_principal_produto(16)
    assert valor == 22.0


def test_produto_sem_principal_nem_app_continua_recusado(monkeypatch):
    monkeypatch.setattr(database.db, 'execute_query', lambda q, p=None, **k: None)
    monkeypatch.setattr(database, 'get_app_produto', lambda pid: None)
    assert database.get_ebook_principal_produto(99) is None
    assert database.resolver_valor_principal_produto(99) == (None, None)


def test_item_principal_do_app_sem_arquivo(monkeypatch):
    sqls = []
    monkeypatch.setattr(database.db, 'execute_query', lambda q, p=None, **k: sqls.append((q, p)))
    monkeypatch.setattr(database.db, 'execute_many', lambda q, lista: sqls.append((q, lista)))
    monkeypatch.setattr(database, 'listar_ebooks_bonus_produto', lambda pid: [])
    principal = {**APP, 'id': None, 'path_arquivo': None, 'nome_arquivo': None}
    database.criar_itens_pedido_web(500, 16, principal, 22.0)
    q, params = sqls[0]
    assert 'app_slug' in q and 'path_arquivo' not in q
    assert params == (500, 'fatia', 'App Fatias — Plano Guiado', 22.0)


def test_estante_nao_lista_o_app_como_livro(monkeypatch):
    import importlib
    checkout = importlib.import_module('web.checkout')  # 'from web import checkout' pega a rota
    itens = [{'id': 1, 'tipo': 'principal', 'ebook_id': None, 'path_arquivo': None, 'nome': 'App'},
             {'id': 2, 'tipo': 'bonus', 'ebook_id': 7, 'path_arquivo': 'f.pdf', 'nome': 'Fatias que Vendem'}]
    monkeypatch.setattr(database, 'listar_itens_pedido_ebook', lambda pid: itens)
    monkeypatch.setattr(database, 'listar_pedidos_pagos_relacionados', lambda *a: [])
    monkeypatch.setattr(database, 'listar_pedidos_vinculados_pagos', lambda pid: [])
    r = checkout.listar_itens_ebook_do_cliente({'id': 1, 'guid': 'g', 'estado_id': 1000, 'email': 'a@b', 'contact_phone': None})
    assert [i['nome'] for i in r] == ['Fatias que Vendem']


def test_app_em_piloto_nao_e_oferecido_na_estante(monkeypatch):
    """publico=False (piloto): quem não tem o app não o vê no cross-sell; quem tem vê em "Meus apps"."""
    import dataclasses
    import apps
    from apps._nucleo import estante, licenca as lic
    produto = {**APP, 'ativo': 1, 'disponivel_web': 1}
    monkeypatch.setattr(database, 'listar_apps_produto', lambda *a, **k: [produto])
    monkeypatch.setattr(lic, 'buscar_cliente_por_email', lambda e: None)  # cliente sem app
    import web.oferta
    monkeypatch.setattr(web.oferta, 'descontos_dos_produtos', lambda ids: {})
    for publico, esperado in ((False, []), (True, [16])):
        cfg = dataclasses.replace(apps.APPS['fatia'], publico=publico)
        monkeypatch.setattr(estante, 'APPS', {'fatia': cfg})
        meus, ofertas = estante.apps_da_estante({'email': 'x@y.com'})
        assert meus == [] and [o['produto_id'] for o in ofertas] == esperado
