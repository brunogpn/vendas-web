"""Textos dos e-mails da Música (o corpo; a moldura com as cores do produto vem do notificador).
Público 35+: frases curtas, um botão grande."""
import html


def _p(texto):
    return f'<p style="font-size:18px; line-height:1.5; color:#1e1e1c; margin:0 0 16px;">{texto}</p>'


def _botao(rotulo, url):
    return (f'<p style="margin:24px 0; text-align:center;"><a href="{html.escape(url)}" '
            f'style="display:inline-block; background:#E11D48; color:#ffffff; text-decoration:none; font-size:18px; '
            f'font-weight:bold; padding:16px 28px; border-radius:16px;">{html.escape(rotulo)}</a></p>')


def presente(nome_quem_recebe, de, titulo, mensagem, link):
    """E-mail para quem ganha a música (com cópia para quem comprou). Só o link: nada anexado."""
    e = html.escape
    corpo = _p(f'Oi, {e(nome_quem_recebe)}!')
    corpo += _p(f'<b>{e(de)}</b> preparou uma surpresa para você: uma música feita só para você 🎁🎵')
    if mensagem:
        corpo += _p(f'<i>“{e(mensagem)}”</i>')
    corpo += _botao(f'Ouvir “{titulo}”', link)
    corpo += _p('Na página você ouve, baixa e guarda a música.')
    return f'{de} fez uma música para você 🎵', corpo


def presente_nao_entregue(nome_quem_recebe, email, link, tentativas):
    """Para quem comprou: o e-mail do presente não chegou em nenhuma tentativa (quase sempre caixa lotada)."""
    e = html.escape
    corpo = _p(f'Tentamos {tentativas} vezes, mas o e-mail com a música não chegou para <b>{e(nome_quem_recebe)}</b> '
               f'({e(email)}). Quase sempre é a caixa de e-mail cheia.')
    corpo += _p('Você recebeu uma cópia de cada envio. Para entregar o presente, mande este link para '
                f'{e(nome_quem_recebe)} pelo WhatsApp ou por mensagem:')
    corpo += _botao('Abrir a música do presente', link)
    corpo += _p(f'<span style="font-size:15px; color:#555;">{e(link)}</span>')
    return f'Não conseguimos entregar a música para {nome_quem_recebe}', corpo


def lembrete(numero, de, para, link):
    """Para quem ouviu a prévia e não comprou (1 h e 24 h depois)."""
    e = html.escape
    if numero == 1:
        assunto = f'A música de {para} está te esperando 🎶'
        corpo = _p(f'Oi, {e(de)}!') + _p(f'A música que você criou para <b>{e(para)}</b> ficou linda. '
                                           'Falta só liberar a versão completa.')
    else:
        assunto = f'A música de {para} ainda está guardada aqui'
        corpo = _p(f'{e(de)}, imagina a reação de <b>{e(para)}</b> ouvindo o próprio nome cantado 💛') + \
            _p('A música continua guardada. Ouça de novo:')
    return assunto, corpo + _botao('Ouvir a minha música', link)
