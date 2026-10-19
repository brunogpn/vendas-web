"""GeradorMusica pela Apiframe → Suno (MVP). Para trocar de provedor, ver gerador_suno.py.

Documentação: https://apiframe.ai/docs/music/suno e https://apiframe.ai/docs/webhooks
Cada geração custa 11 créditos e devolve 2 versões (faixas).
"""
import hashlib
import hmac
import json
import logging

import requests

from musica.dominio.modelos import (GERACAO_ANDAMENTO, GERACAO_FALHOU, GERACAO_PRONTA, ErroGerador, Faixa,
                                    PedidoGeracao, ResultadoGeracao)

log = logging.getLogger(__name__)

URL_API = 'https://api.apiframe.ai/v2'
STATUS_FALHA = {'FAILED', 'ERROR', 'CANCELED', 'CANCELLED', 'TIMEOUT'}


class GeradorApiframe:
    nome = 'apiframe'

    def __init__(self, chave: str, versao_suno: str):
        self.chave, self.versao_suno = chave, versao_suno

    def criar(self, pedido: PedidoGeracao, webhook_url: str | None) -> str:
        if not self.chave:
            raise ErroGerador('APIFRAME_API_KEY não configurada')
        corpo = {
            'model': 'suno',
            'prompt': pedido.letra,
            'sunoParams': {
                'custom_mode': True,       # o prompt é a nossa letra
                'auto_lyrics': False,
                'instrumental': False,
                'model_version': self.versao_suno,
                'title': pedido.titulo[:80],
                'style': pedido.estilo[:1000],
                'negative_tags': pedido.negativo[:500],
                'vocal_gender': pedido.genero_vocal,
            },
        }
        if webhook_url:
            corpo['webhookUrl'] = webhook_url
            corpo['webhookEvents'] = ['completed', 'failed']
        try:
            resposta = requests.post(f'{URL_API}/music/generate', headers={'X-API-Key': self.chave}, json=corpo,
                                     timeout=30)
        except requests.RequestException as erro:
            raise ErroGerador('sem conexão com a Apiframe') from erro
        if resposta.status_code >= 400:
            raise ErroGerador(f'Apiframe recusou o pedido ({resposta.status_code}): {resposta.text[:300]}')
        return resposta.json()['jobId']

    def consultar(self, job_id: str) -> ResultadoGeracao:
        try:
            resposta = requests.get(f'{URL_API}/jobs/{job_id}', headers={'X-API-Key': self.chave}, timeout=20)
            resposta.raise_for_status()
        except requests.RequestException as erro:
            log.warning(f'[MUSICA-APIFRAME] Falha ao consultar o job {job_id}: {erro}')
            return ResultadoGeracao(GERACAO_ANDAMENTO)   # tenta de novo na próxima consulta
        try:
            return interpretar_job(resposta.json())
        except ValueError:   # corpo que não é JSON: tenta de novo na próxima consulta
            log.warning(f'[MUSICA-APIFRAME] Resposta inválida ao consultar o job {job_id}')
            return ResultadoGeracao(GERACAO_ANDAMENTO)

    def webhook_valido(self, corpo: bytes, cabecalhos: dict) -> str | None:
        """O segredo é o SHA-256 da chave da API; a assinatura é o HMAC-SHA256 do corpo."""
        assinatura = cabecalhos.get('X-Webhook-Signature') or ''
        if not self.chave or not assinatura:
            return None
        segredo = hashlib.sha256(self.chave.encode()).hexdigest().encode()
        esperado = hmac.new(segredo, corpo, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(esperado, assinatura.removeprefix('sha256=')):
            return None
        try:
            return str(json.loads(corpo).get('jobId') or '') or None
        except (ValueError, AttributeError):
            return None


def interpretar_job(dados: dict) -> ResultadoGeracao:
    status = (dados.get('status') or '').upper()
    if status == 'COMPLETED':
        faixas = [Faixa(f['audioUrl'], f.get('duration')) for f in (dados.get('result') or {}).get('tracks') or []
                  if isinstance(f, dict) and f.get('audioUrl')]
        if not faixas:
            return ResultadoGeracao(GERACAO_FALHOU, erro='terminou sem nenhuma faixa com áudio')
        return ResultadoGeracao(GERACAO_PRONTA, faixas)
    if status in STATUS_FALHA:
        return ResultadoGeracao(GERACAO_FALHOU, erro=str(dados.get('error') or status))
    return ResultadoGeracao(GERACAO_ANDAMENTO)
