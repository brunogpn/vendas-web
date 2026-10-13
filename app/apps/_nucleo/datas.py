"""Datas dos apps, sempre no fuso de Brasília.

As telas e as regras (licença, trilha, vendas) trabalham com o *dia* em Brasília, não com a hora:
o dia do vencimento ainda vale, uma tarefa feita às 23h conta para hoje etc.
"""
import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo('America/Sao_Paulo')

MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
         'setembro', 'outubro', 'novembro', 'dezembro']
# date.weekday(): segunda = 0 ... domingo = 6
SEMANA = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']


def agora() -> datetime.datetime:
    """Data e hora de Brasília, sem fuso (como o MySQL dos containers, que já roda em Brasília)."""
    return datetime.datetime.now(FUSO).replace(tzinfo=None)


def hoje() -> datetime.date:
    return datetime.datetime.now(FUSO).date()


def como_data(valor) -> datetime.date | None:
    """Aceita date, datetime ou 'AAAA-MM-DD' (o que vem do banco ou de um formulário)."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    return datetime.date.fromisoformat(str(valor)[:10])


def dias_entre(de, ate) -> int:
    return (como_data(ate) - como_data(de)).days


def mes_atual() -> str:
    """'AAAA-MM' de hoje."""
    return hoje().isoformat()[:7]


def nome_mes(mes: str) -> str:
    """'2026-10' → 'outubro'."""
    return MESES[int(mes[5:7]) - 1]


def por_extenso(data) -> str:
    """'segunda, 12 de outubro' (a tela põe a primeira letra em maiúscula)."""
    d = como_data(data)
    return f'{SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]}'


def curta(data) -> str:
    """'12/10'."""
    d = como_data(data)
    return f'{d.day:02d}/{d.month:02d}'


def completa(data) -> str:
    """'12/10/2026'."""
    d = como_data(data)
    return f'{d.day:02d}/{d.month:02d}/{d.year}'
