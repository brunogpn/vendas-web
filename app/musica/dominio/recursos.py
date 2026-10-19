"""O que um entregável do tipo música libera (entregaveis.recurso → pedido_itens.recurso).

Fica num arquivo SEM dependências: o admin e o checkout de todos os produtos importam daqui, e um problema no
resto do módulo da Música não pode derrubar a venda dos e-books.
"""

MUSICA = 'musica'                      # a música (2 versões): ouvir, baixar, letra
VIDEOCLIPE = 'videoclipe'              # videoclipe com as fotos da cliente
QRCODE = 'qrcode'                      # cartão com QR code para imprimir
ENTREGA_EMAIL = 'entrega_email'        # e-mail para quem recebe o presente (cópia para quem comprou)
ENTREGA_WHATSAPP = 'entrega_whatsapp'  # preparado; sem número de WhatsApp, não é vendido

# papel: em que papel o recurso pode entrar num plano.
RECURSOS = {
    MUSICA: {'nome': 'Música (2 versões, ouvir e baixar)', 'papel': 'principal'},
    VIDEOCLIPE: {'nome': 'Videoclipe com as fotos', 'papel': 'principal'},
    QRCODE: {'nome': 'Cartão com QR code', 'papel': 'bump'},
    ENTREGA_EMAIL: {'nome': 'Entrega por e-mail para quem recebe', 'papel': 'bump'},
    ENTREGA_WHATSAPP: {'nome': 'Entrega no WhatsApp de quem recebe (não vendido ainda)', 'papel': 'bump'},
}


def papel_permitido(recurso: str, papel: str) -> bool:
    """Principal (música, videoclipe) só como principal; serviços (QR, entregas) só como order bump."""
    info = RECURSOS.get(recurso)
    return bool(info) and info['papel'] == papel


def plano_vende_musica(plano: dict | None) -> bool:
    """Plano com item de música como principal (get_plano_venda): só se compra a partir de uma prévia."""
    return bool(plano) and any(p.get('tipo') == 'musica' for p in plano.get('principais') or [])
