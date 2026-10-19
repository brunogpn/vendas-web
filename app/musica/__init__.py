"""Produto Música (Música de Presente): quiz → letra por IA → música (gerador na borda) → prévia → checkout → música.
Arquitetura (portas e adaptadores) e operação: docs/MUSICA.md.

  dominio/        regras puras (status, estilo, prévia, legenda, recursos vendidos)
  portas.py       o que os casos de uso precisam de fora (GeradorMusica, EscritorLetra, Repositorio, ...)
  adaptadores/    quem atende cada porta (Apiframe, OpenAI, ffmpeg, MySQL, Gmail, Celery)
  fabrica.py      escolhe os adaptadores pelo .env (MUSICA_GERADOR=apiframe|suno|simulado)
  casos_de_uso.py o fluxo; rotas.py e tarefas.py só traduzem HTTP/Celery para ele
  integracao.py   o que o resto do sistema (checkout, e-mail, Estante) usa daqui
"""
import logging


def registrar(flask_app):
    """Registra /musica/... Um problema no módulo deixa só a Música fora do ar, nunca o resto do site."""
    try:
        from musica.rotas import bp
        flask_app.register_blueprint(bp)
        import config
        from musica import config as cfg_musica
        if config.EH_PRODUCAO and not cfg_musica.TURNSTILE_SECRET:
            logging.getLogger(__name__).warning('[MUSICA] Produção sem anti-robô (TURNSTILE_SECRET): cada quiz enviado '
                                                'gasta uma letra na OpenAI — ligar o Turnstile antes dos anúncios')
    except Exception as e:
        logging.getLogger(__name__).error(f'[MUSICA] Módulo NÃO carregado (fora do ar): {e}')
