"""GeradorMusica direto numa conta própria do Suno (sem a Apiframe) — AINDA NÃO IMPLEMENTADO.

Para trocar de provedor:
1. Implemente aqui os 3 métodos da porta portas.GeradorMusica (criar, consultar, webhook_valido),
   devolvendo os mesmos objetos de dominio/modelos.py (PedidoGeracao → job_id → ResultadoGeracao).
2. MUSICA_GERADOR=suno no .env (fabrica.py escolhe este adaptador). Nada mais no módulo muda.

Antes: confirmar se o Suno oferece acesso oficial por API para uso comercial (as "APIs do Suno" conhecidas
são de terceiros, como a Apiframe) e os direitos de uso das músicas geradas.
"""
from musica.dominio.modelos import ErroGerador, PedidoGeracao, ResultadoGeracao


class GeradorSuno:
    nome = 'suno'

    def __init__(self, **credenciais):
        self.credenciais = credenciais

    def criar(self, pedido: PedidoGeracao, webhook_url: str | None) -> str:
        raise ErroGerador('Gerador Suno direto ainda não implementado (use MUSICA_GERADOR=apiframe)')

    def consultar(self, job_id: str) -> ResultadoGeracao:
        raise ErroGerador('Gerador Suno direto ainda não implementado')

    def webhook_valido(self, corpo: bytes, cabecalhos: dict) -> str | None:
        return None
