"""GeradorMusica de mentira, para o dev e os testes: não gasta crédito; fica 'pronta' alguns segundos depois
com duas faixas 'simulado' (o adaptador de áudio gera um tom de 2min30 no lugar do download)."""
import time

from musica.dominio.modelos import GERACAO_ANDAMENTO, GERACAO_PRONTA, Faixa, PedidoGeracao, ResultadoGeracao

URL_SIMULADA = 'simulado'


class GeradorSimulado:
    nome = 'simulado'

    def __init__(self, segundos_ate_pronta: float = 6):
        self.segundos = segundos_ate_pronta

    def criar(self, pedido: PedidoGeracao, webhook_url: str | None) -> str:
        return f'simulado-{int(time.time() * 1000)}'   # milissegundos (sem arredondar para o futuro)

    def consultar(self, job_id: str) -> ResultadoGeracao:
        criado = int(job_id.split('-', 1)[1]) / 1000
        if time.time() - criado < self.segundos:
            return ResultadoGeracao(GERACAO_ANDAMENTO)
        return ResultadoGeracao(GERACAO_PRONTA, [Faixa(URL_SIMULADA, 150.0), Faixa(URL_SIMULADA, 150.0)])

    def webhook_valido(self, corpo: bytes, cabecalhos: dict) -> str | None:
        return None
