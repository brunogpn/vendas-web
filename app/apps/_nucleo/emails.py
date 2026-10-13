"""E-mails dos apps: código de login e avisos de vencimento.

Usa o mesmo envio do resto do sistema (Gmail API, fluxos/_email_gmail). Fora de produção NADA é
enviado: o código aparece na tela de login e os e-mails vão só para o log — o dev tem banco
isolado, mas o envio pelo Gmail é real.
"""
import html
import logging

import config
from apps._nucleo import datas

logger = logging.getLogger(__name__)


def _enviar(cfg, para: str, assunto: str, corpo_html: str) -> None:
    if not config.EH_PRODUCAO:
        logger.info(f"[APPS][DEV] E-mail NÃO enviado para {para}: {assunto}")
        return
    from fluxos._email_gmail import enviar, wrapper_html
    pagina = wrapper_html(
        titulo_header=html.escape(cfg.nome), corpo_interno_html=corpo_html,
        nome_remetente=cfg.nome_remetente, cor_primaria=cfg.cor_botao_email,
        cor_secundaria=cfg.cor_botao_email,
        rodape=f'Dúvidas? Responda este e-mail ou escreva para {html.escape(cfg.email_suporte)}.')
    enviar(destinatario=para, remetente=cfg.email_remetente, nome_remetente=cfg.nome_remetente,
           subject=assunto, html=pagina)


def _p(texto: str, estilo: str = '') -> str:
    return f'<p style="font-size:18px; line-height:1.5; color:#1e1e1c; margin:0 0 16px; {estilo}">{texto}</p>'


def _botao(cfg, rotulo: str, url: str) -> str:
    return (f'<p style="margin:24px 0; text-align:center;"><a href="{html.escape(url)}" '
            f'style="display:inline-block; background:{cfg.cor_botao_email}; color:#ffffff; text-decoration:none; '
            f'font-size:18px; font-weight:bold; padding:16px 28px; border-radius:16px;">{html.escape(rotulo)}</a></p>')


def enviar_codigo(cfg, para: str, codigo: str) -> None:
    corpo = (
        _p(f'Olá! Seu código para entrar no {html.escape(cfg.nome)} é:')
        + f'<p style="font-size:36px; font-weight:bold; letter-spacing:8px; text-align:center; '
          f'color:#1e1e1c; margin:8px 0 24px;">{codigo}</p>'
        + _p('Ele vale por 15 minutos.')
        + _p('Se não foi você que pediu, pode ignorar este email.', 'color:#5e5b56; font-size:16px;')
    )
    _enviar(cfg, para, f'Seu código de acesso: {codigo}', corpo)


def _quando(dias: int) -> str:
    if dias <= 0:
        return 'hoje'
    if dias == 1:
        return 'amanhã'
    return f'em {dias} dias'


def enviar_aviso_vencimento(cfg, para: str, nome: str | None, expira_em, dias: int, link_acesso: str) -> None:
    primeiro = (nome or '').strip().split(' ')[0]
    saudacao = f'Olá, {html.escape(primeiro)}!' if primeiro else 'Olá!'
    quando = _quando(dias)
    corpo = (
        _p(saudacao, 'font-size:22px; font-weight:bold;')
        + _p(f'Passando para avisar: seu acesso ao {html.escape(cfg.nome)} vence {quando}, '
             f'no dia {datas.completa(expira_em)}.')
        + _p('Renovando, você continua com a trilha, as receitas, a calculadora e o controle das suas vendas. '
             'Todo o seu progresso fica guardado.')
        + _botao(cfg, 'Renovar meu acesso', link_acesso)
    )
    _enviar(cfg, para, f'Seu acesso ao {cfg.nome} vence {quando}', corpo)
