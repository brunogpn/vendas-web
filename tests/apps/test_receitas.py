import pytest

from apps.fatia import receitas as rec


def test_conteudo_do_bruno_lido_inteiro():
    cats = {}
    for r in rec.RECEITAS:
        cats[r['categoria']] = cats.get(r['categoria'], 0) + 1
    assert len(rec.RECEITAS) == 84
    assert cats['fatias'] == 33 and cats['brigadeiros'] == 10
    assert len(rec.RECEITAS_DE_VENDA) == 43


def test_receita_custo_soma_bases_usadas():
    r = rec.receita('ninho-com-nutella')
    c = rec.receita_custo(r)
    itens = {i['item']: i['qtd'] for i in c['itens']}
    assert itens['ovo'] == 3
    # usa a calda de leite Ninho: os ingredientes dela entram na conta
    base = rec.receita('calda-leite-ninho')
    for it in rec.itens_da_receita(base['id']):
        assert it['item'] in itens


def test_base_citada_prefere_cobertura():
    assert rec.base_citada('Ganache meio amarga')['categoria'] == 'coberturas'
    assert rec.base_citada('Massa Black')['id'] == 'massa-black'
    assert rec.base_citada('Coisa que não existe') is None


def test_erros_no_texto_param_a_leitura(tmp_path):
    (tmp_path / 'x.txt').write_text(
        '@ a | Fatia A | fatias | 1\n## Massa\n- 3 ovos [ovo 3]\n- 1 coisa [nao-existe 1]\nlinha estranha\n'
        '@ a | Repetida | fatias | 2\nusa: fantasma\n', encoding='utf-8')
    with pytest.raises(rec.ErroReceitas) as e:
        rec.ler_receitas(str(tmp_path), str(tmp_path))
    msg = str(e.value)
    assert 'id repetido: a' in msg
    assert 'ingrediente desconhecido "nao-existe"' in msg
    assert 'não entendi "linha estranha"' in msg
    assert 'usa receita inexistente "fantasma"' in msg
