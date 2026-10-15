"""Desconto de oferta (popup / Estante, migration 083): token assinado + desconto vindo do banco."""
import pytest

from web import oferta

AGORA = 1_800_000_000.0


def test_token_valido_so_para_o_produto_e_dentro_da_validade():
    t = oferta.gerar_token(16, agora=AGORA)
    assert oferta.validar_token(t, 16, agora=AGORA + 3600)
    assert not oferta.validar_token(t, 12, agora=AGORA)                              # outro produto
    assert not oferta.validar_token(t, 16, agora=AGORA + oferta.VALIDADE_SEGUNDOS + 1)  # vencido


@pytest.mark.parametrize('token', [None, '', 'abc', '123', '123.abc', '9999999999.' + 'f' * 24])
def test_token_invalido_ou_adulterado(token):
    assert not oferta.validar_token(token, 16, agora=AGORA)


def test_validade_adulterada_invalida_a_assinatura():
    expira, assinatura = oferta.gerar_token(16, agora=AGORA).split('.')
    assert not oferta.validar_token(f'{int(expira) + 999999}.{assinatura}', 16, agora=AGORA)


@pytest.fixture
def banco(monkeypatch):
    estado = {'desconto': 7.0, 'updates': []}

    def execute_query(sql, params=None, **kw):
        if sql.startswith('SELECT desconto_oferta'):
            return {'desconto_oferta': estado['desconto']}
        estado['updates'].append(params)
    monkeypatch.setattr(oferta.db, 'execute_query', execute_query)
    return estado


def test_desconto_so_com_token_valido(banco):
    assert oferta.desconto_da_oferta(None, 16, 22.0) == 0
    assert oferta.desconto_da_oferta('lixo', 16, 22.0) == 0
    assert oferta.desconto_da_oferta(oferta.gerar_token(12), 16, 22.0) == 0   # token de outro produto
    assert oferta.desconto_da_oferta(oferta.gerar_token(16), 16, 22.0) == 7.0


def test_desconto_maior_ou_igual_ao_preco_e_ignorado(banco):
    # Ex.: o preço foi baixado depois de cadastrar a oferta — preço cheio, nunca venda por centavos.
    banco['desconto'] = 50.0
    assert oferta.desconto_do_produto(16, 22.0) == 0
    banco['desconto'] = 22.0
    assert oferta.desconto_do_produto(16, 22.0) == 0
    banco['desconto'] = 0
    assert oferta.desconto_do_produto(16, 22.0) == 0
    assert oferta.desconto_valido(7, 22) == 7.0


def test_desconto_divergente_do_que_a_tela_mostrou():
    assert oferta.oferta_divergente({'desconto_exibido': 7}, 7.0) is None
    assert oferta.oferta_divergente({}, 0.0) is None                       # checkout normal
    assert oferta.oferta_divergente({'desconto_exibido': '7.00'}, 0.0)['oferta_alterada']  # token venceu
    assert oferta.oferta_divergente({'desconto_exibido': 0}, 7.0)['oferta_alterada']


def test_grava_no_pedido_so_quando_ha_desconto_ou_retry(banco):
    oferta.gravar_desconto_pedido(1, 0)
    assert banco['updates'] == []
    oferta.gravar_desconto_pedido(1, 7)
    oferta.gravar_desconto_pedido(2, 0, sempre=True)   # retry de cartão negado sem a oferta: zera
    assert banco['updates'] == [(7, 1), (0, 2)]


def test_vitrine_com_oferta_mostra_preco_com_desconto_e_token():
    item = {'produto_id': 14, 'preco_promocional': 6.9, 'nome_venda': 'X'}
    assert oferta.aplicar_na_vitrine(item, {}) is item                      # sem oferta: igual
    com = oferta.aplicar_na_vitrine(item, {14: 2.0})
    assert com['preco_promocional'] == 4.9 and com['preco_cheio'] == 6.9
    assert oferta.validar_token(com['oferta'], 14)
    assert oferta.aplicar_na_vitrine(item, {14: 99}) is item              # desconto >= preço: ignora


@pytest.mark.parametrize('estado,desconto,retoma', [
    (1002, 0, False),   # PIX de preço cheio não pago: a oferta abre pedido novo com desconto
    (1001, 0, False),
    (1006, 0, False),
    (1007, 0, False),
    (1005, 0, True),    # cartão em autorização/timeout: pode já ter sido cobrado — SEMPRE retoma
    (1000, 0, True),    # pago
    (1002, 7, True),    # já tem o desconto: retoma o próprio
])
def test_oferta_nao_abandona_pedido_com_cobranca_possivel(monkeypatch, estado, desconto, retoma):
    import importlib
    import database
    web = importlib.import_module('web')
    monkeypatch.setattr(database, 'get_pedido', lambda i: {'id': i, 'estado_id': estado, 'desconto': desconto})
    assert (web._retomar_sem_perder_oferta(10, 'token') == 10) is retoma
    assert web._retomar_sem_perder_oferta(10, None) == 10   # sem oferta: retomada de sempre
