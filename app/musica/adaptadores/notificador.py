"""Notificador: e-mail pelo Gmail do sistema (fluxos/_email_gmail), WhatsApp preparado e desligado,
e alerta para a equipe.

Fora de produção NADA é enviado por e-mail (vai só para o log), como nos apps: o dev tem banco
isolado, mas o envio pelo Gmail é real.
"""
import html
import logging
import os

import config

logger = logging.getLogger(__name__)

# Modelos de mensagem para cadastrar e aprovar na Meta quando o produto tiver número de WhatsApp.
# {{1}}, {{2}}... são preenchidos na ordem da lista `variaveis`.
MODELOS_WHATSAPP = {
    'musica_pronta': {'categoria': 'UTILITY',
                      'texto': 'Oi, {{1}}! A música para {{2}} ficou pronta 🎵\nOuça, baixe e envie para quem você ama: {{3}}'},
    'previa_esperando': {'categoria': 'MARKETING',
                         'texto': 'Oi, {{1}}! A música que você criou para {{2}} está te esperando 🎶\n'
                                  'Falta só liberar a versão completa: {{3}}'},
    'presente_agendado': {'categoria': 'UTILITY',
                          'texto': 'Oi, {{1}}! {{2}} preparou uma surpresa para você: uma música feita só sua 🎁🎵\n'
                                   'Aperte o play: {{3}}'},
}


class Notificador:
    def __init__(self, repositorio, whatsapp_ativo: bool = False):
        self.repositorio, self.whatsapp_ativo = repositorio, whatsapp_ativo

    def email(self, produto_id, destino, assunto, html_corpo, cc=None):
        if not config.EH_PRODUCAO:
            logger.info(f'[MUSICA][DEV] E-mail NÃO enviado para {destino} (cc {cc}): {assunto}')
            return 'dev-sem-envio'   # "enviado" no dev: a manutenção não o reenvia como envio interrompido
        from fluxos._email_gmail import enviar, wrapper_html
        produto = self.repositorio.remetente_do_produto(produto_id)
        nome = produto.get('email_nome_remetente') or produto.get('nome') or 'Música de Presente'
        remetente = produto.get('email_remetente') or os.getenv('EMAIL_FROM', '')
        cor = produto.get('email_cor_primaria') or '#E11D48'
        pagina = wrapper_html(titulo_header=html.escape(nome), corpo_interno_html=html_corpo, nome_remetente=nome,
                              cor_primaria=cor, cor_secundaria=produto.get('email_cor_secundaria') or cor,
                              rodape=f'Dúvidas? É só responder este e-mail. {html.escape(nome)}')
        resultado = enviar(destinatario=destino, remetente=remetente, nome_remetente=nome, subject=assunto, html=pagina,
                           cc=cc) or {}
        return resultado.get('threadId')

    def whatsapp(self, telefone, modelo, variaveis):
        # Sem número de WhatsApp para o produto ainda: preparado, mas só registra. Quando houver, enviar o
        # modelo aprovado pela API oficial (config.WHATSAPP_API_URL) ou pelo gateway, como nos outros fluxos.
        if not self.whatsapp_ativo:
            logger.info(f'[MUSICA] WhatsApp desligado: {modelo} para {telefone} não enviado')
            return
        logger.warning(f'[MUSICA] WhatsApp ligado mas o envio ainda não foi implementado ({modelo})')

    def equipe(self, mensagem):
        logger.error(f'[MUSICA][ALERTA] {mensagem}')
        try:
            from whatsapp import notificar_admin_erro_sistema
            notificar_admin_erro_sistema(f'MUSICA | {mensagem}'[:300], log='log_worker')
        except Exception as e:
            logger.error(f'[MUSICA] Falha ao avisar a equipe: {e}')
