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


def test_desconto_nunca_zera_o_preco(banco):
    banco['desconto'] = 50.0
    assert oferta.desconto_do_produto(16, 22.0) == 21.99
    banco['desconto'] = 0
    assert oferta.desconto_do_produto(16, 22.0) == 0


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
    assert oferta.aplicar_na_vitrine(item, {14: 99})['preco_promocional'] == 0.01  # nunca zera
