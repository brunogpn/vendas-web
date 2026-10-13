"""Números e dinheiro no padrão brasileiro (mesmas regras do static/apps/_nucleo/app.js)."""
import math
import re


def reais(valor) -> str:
    """1234.5 → 'R$ 1.234,50'."""
    valor = float(valor or 0)
    sinal = '-' if valor < 0 else ''
    texto = f'{abs(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{sinal}R$ {texto}'


def reais_sem_centavos(valor) -> str:
    """1234.5 → 'R$ 1.235' (arredonda, como o Intl do navegador)."""
    valor = float(valor or 0)
    sinal = '-' if valor < 0 else ''
    inteiro = math.floor(abs(valor) + 0.5)
    return f'{sinal}R$ {inteiro:,}'.replace(',', '.')


_MILHAR = re.compile(r'^-?\d{1,3}(\.\d{3})+$')


def ler_numero(texto) -> float:
    """Lê o que a cliente digitou: '12,50', '12.50', 'R$ 1.234,56', '1.000'.

    Com vírgula, a vírgula é o decimal e os pontos são milhar. Sem vírgula, um ponto seguido de
    exatamente 3 dígitos (em todos os grupos) é milhar — '1.000' é mil, não 1 (no app original
    '1.000' virava 1). Qualquer outra coisa ilegível vira 0.
    """
    if texto is None:
        return 0.0
    if isinstance(texto, (int, float)):
        return float(texto) if math.isfinite(texto) else 0.0
    limpo = re.sub(r'[^\d,.\-]', '', str(texto))
    if ',' in limpo:
        normal = limpo.replace('.', '').replace(',', '.', 1)
    elif _MILHAR.match(limpo):
        normal = limpo.replace('.', '')
    else:
        normal = limpo
    try:
        n = float(normal)
    except ValueError:
        return 0.0
    return n if math.isfinite(n) else 0.0
