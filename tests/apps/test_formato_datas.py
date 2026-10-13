import datetime

from apps._nucleo import datas, formato


def test_ler_numero_aceita_o_que_a_cliente_digita():
    assert formato.ler_numero('12,50') == 12.5
    assert formato.ler_numero('12.50') == 12.5
    assert formato.ler_numero('R$ 1.234,56') == 1234.56
    assert formato.ler_numero('') == 0
    assert formato.ler_numero(None) == 0
    assert formato.ler_numero('abc') == 0
    assert formato.ler_numero(7) == 7


def test_ler_numero_ponto_de_milhar_sem_virgula():
    # No app original "1.000" virava 1 — a meta de R$ 1.000 digitada assim ficava R$ 1.
    assert formato.ler_numero('1.000') == 1000
    assert formato.ler_numero('10.000') == 10000
    assert formato.ler_numero('1.5') == 1.5


def test_reais():
    assert formato.reais(1234.5) == 'R$ 1.234,50'
    assert formato.reais(-3) == '-R$ 3,00'
    assert formato.reais_sem_centavos(1234.5) == 'R$ 1.235'
    assert formato.reais_sem_centavos(1000) == 'R$ 1.000'


def test_datas_por_extenso_e_curta():
    d = datetime.date(2026, 10, 12)  # segunda-feira
    assert datas.por_extenso(d) == 'segunda, 12 de outubro'
    assert datas.curta('2026-10-05') == '05/10'
    assert datas.completa(d) == '12/10/2026'
    assert datas.dias_entre('2026-10-12', '2026-10-19') == 7
    assert datas.nome_mes('2026-03') == 'março'
