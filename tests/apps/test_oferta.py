"""Desconto de oferta (popup / Estante): token assinado por produto e plano + desconto do plano (migration 085)."""
import pytest

from web import oferta

AGORA = 1_800_000_000.0


def test_token_valido_so_para_o_produto_e_plano_e_dentro_da_validade():
    t = oferta.gerar_token(12, 30, agora=AGORA)
    assert oferta.validar_token(t, 12, 30, agora=AGORA + 3600)
    assert not oferta.validar_token(t, 16, 30, agora=AGORA)                              # outro produto
    assert not oferta.validar_token(t, 12, 8, agora=AGORA)                               # outro plano (ex.: Básico)
    assert not oferta.validar_token(t, 12, 30, agora=AGORA + oferta.VALIDADE_SEGUNDOS + 1)  # vencido


def test_token_antigo_sem_plano_vale_so_no_plano_padrao():
    # Links emitidos antes da migration 085 (só produto): continuam valendo até vencer, no plano padrão.
    import hashlib
    import hmac
    import os
    expira = int(AGORA + 3600)
    segredo = (os.getenv('SECRET_KEY') or 'troque-em-producao').encode()
    antigo = f"{expira}." + hmac.new(segredo, f'oferta:16:{expira}'.encode(), hashlib.sha256).hexdigest()[:24]
    assert oferta.validar_token(antigo, 16, 7, agora=AGORA, plano_padrao=True)
    assert not oferta.validar_token(antigo, 16, 7, agora=AGORA)                    # plano que não é o padrão
    assert not oferta.validar_token(antigo, 12, 7, agora=AGORA, plano_padrao=True)  # outro produto
    assert not oferta.validar_token(antigo, 16, 7, agora=expira + 1, plano_padrao=True)  # vencido


@pytest.mark.parametrize('token', [None, '', 'abc', '123', '123.abc', '9999999999.' + 'f' * 24])
def test_token_invalido_ou_adulterado(token):
    assert not oferta.validar_token(token, 16, 1, agora=AGORA)


def test_validade_adulterada_invalida_a_assinatura():
    expira, assinatura = oferta.gerar_token(16, 1, agora=AGORA).split('.')
    assert not oferta.validar_token(f'{int(expira) + 999999}.{assinatura}', 16, 1, agora=AGORA)


@pytest.fixture
def banco(monkeypatch):
    estado = {'updates': []}

    def execute_query(sql, params=None, **kw):
        estado['updates'].append(params)
    monkeypatch.setattr(oferta.db, 'execute_query', execute_query)
    return estado


COMPLETO = {'id': 30, 'produto_id': 12, 'desconto_oferta': 7.0}


def test_desconto_so_com_token_valido_para_o_plano():
    assert oferta.desconto_da_oferta(None, COMPLETO, 22.0) == 0
    assert oferta.desconto_da_oferta('lixo', COMPLETO, 22.0) == 0
    assert oferta.desconto_da_oferta(oferta.gerar_token(16, 30), COMPLETO, 22.0) == 0   # token de outro produto
    assert oferta.desconto_da_oferta(oferta.gerar_token(12, 8), COMPLETO, 22.0) == 0    # token do Básico
    assert oferta.desconto_da_oferta(oferta.gerar_token(12, 30), COMPLETO, 22.0) == 7.0


def test_desconto_maior_ou_igual_ao_preco_e_ignorado():
    # Ex.: o preço foi baixado depois de cadastrar a oferta — preço cheio, nunca venda por centavos.
    assert oferta.desconto_do_plano({**COMPLETO, 'desconto_oferta': 50.0}, 22.0) == 0
    assert oferta.desconto_do_plano({**COMPLETO, 'desconto_oferta': 22.0}, 22.0) == 0
    assert oferta.desconto_do_plano({**COMPLETO, 'desconto_oferta': 0}, 22.0) == 0
    assert oferta.desconto_do_plano({**COMPLETO, 'desconto_oferta': None}, 22.0) == 0
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
    item = {'produto_id': 14, 'plano_id': 9, 'preco_promocional': 6.9, 'nome_venda': 'X', 'desconto_oferta': 0}
    assert oferta.aplicar_na_vitrine(item) is item                          # sem oferta: igual
    com = oferta.aplicar_na_vitrine({**item, 'desconto_oferta': 2.0})
    assert com['preco_promocional'] == 4.9 and com['preco_cheio'] == 6.9
    assert oferta.validar_token(com['oferta'], 14, 9)
    assert not oferta.validar_token(com['oferta'], 14, 10)                  # o token é deste plano
    sem = {**item, 'desconto_oferta': 99}
    assert oferta.aplicar_na_vitrine(sem) is sem                            # desconto >= preço: ignora


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
    plano = {'id': 30, 'padrao': 0}
    monkeypatch.setattr(database, 'get_pedido',
                        lambda i: {'id': i, 'estado_id': estado, 'desconto': desconto, 'plano_id': 30})
    assert (web._retomar_sem_perder_oferta(10, 'token', plano) == 10) is retoma
    assert web._retomar_sem_perder_oferta(10, None, plano) == 10   # sem oferta: retomada de sempre


@pytest.mark.parametrize('pedido,plano,retoma', [
    ({'estado_id': 1000, 'plano_id': 8}, {'id': 30, 'padrao': 0}, False),    # comprou o Básico, abriu o Completo
    ({'estado_id': 1005, 'plano_id': 8}, {'id': 30, 'padrao': 0}, False),    # cartão do Básico em curso: outra compra
    ({'estado_id': 1002, 'plano_id': 30}, {'id': 30, 'padrao': 0}, True),    # mesmo plano: retoma
    ({'estado_id': 1000, 'plano_id': None}, {'id': 8, 'padrao': 1}, True),   # pedido de antes dos planos = padrão
    ({'estado_id': 1000, 'plano_id': None}, {'id': 30, 'padrao': 0}, False),
])
def test_retomada_so_do_mesmo_plano(monkeypatch, pedido, plano, retoma):
    import importlib
    import database
    web = importlib.import_module('web')
    monkeypatch.setattr(database, 'get_pedido', lambda i: {'id': i, 'desconto': 0, **pedido})
    assert (web._retomar_sem_perder_oferta(10, None, plano) == 10) is retoma
