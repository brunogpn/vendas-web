"""Popup "última chance" da prévia da Música: o plano mais caro com desconto de oferta, num link assinado."""
from musica import rotas
from web import oferta


def _plano(pid, slug, padrao, preco, desconto=0, video=False):
    return {'slug': slug, 'nome': slug, 'descricao': '', 'preco': preco, 'videoclipe': video,
            'plano': {'id': pid, 'produto_id': 17, 'slug': slug, 'padrao': padrao, 'desconto_oferta': desconto}}


MUSICA = _plano(18, 'musica', 1, 19.9)


def test_oferta_do_plano_com_video_no_link_assinado():
    o = rotas._oferta_ultima_chance([MUSICA, _plano(19, 'videoclipe', 0, 49.9, desconto=10, video=True)], 'tok')
    assert o['preco'] == rotas.reais(39.9) and o['preco_cheio'] == rotas.reais(49.9) and o['videoclipe']
    assert o['link'].startswith('/pay/17?plano=videoclipe&oferta=') and o['link'].endswith('&musica=tok')
    assert oferta.validar_token(o['link'].split('oferta=')[1].split('&')[0], 17, 19)


def test_sem_desconto_ou_so_o_padrao_nao_ha_oferta():
    assert rotas._oferta_ultima_chance([MUSICA, _plano(19, 'videoclipe', 0, 49.9, video=True)], 't') is None
    assert rotas._oferta_ultima_chance([MUSICA], 't') is None


def test_pula_o_plano_mais_caro_sem_desconto():
    planos = [MUSICA, _plano(19, 'videoclipe', 0, 49.9, desconto=10, video=True), _plano(20, 'premium', 0, 79.9)]
    assert rotas._oferta_ultima_chance(planos, 't')['nome'] == 'videoclipe'


def test_desconto_que_deixa_abaixo_do_padrao_nao_vira_oferta():
    assert rotas._oferta_ultima_chance([MUSICA, _plano(19, 'videoclipe', 0, 49.9, desconto=35, video=True)], 't') is None


def test_erro_ao_montar_nao_derruba_a_previa():
    sem_id = _plano(19, 'videoclipe', 0, 49.9, desconto=10, video=True)
    del sem_id['plano']['id']                                     # com desconto: gerar o link levanta KeyError
    assert rotas._oferta_ultima_chance([MUSICA, sem_id], 't') is None


def test_oferta_diz_quando_o_link_vence():
    import time
    o = rotas._oferta_ultima_chance([MUSICA, _plano(19, 'videoclipe', 0, 49.9, desconto=10, video=True)], 't')
    assert abs(o['expira'] - (time.time() + oferta.VALIDADE_SEGUNDOS)) < 5
