"""Endereços das páginas da Música (para e-mails, QR code e tarefas, que rodam sem requisição)."""
from musica import config


def base(dominio: str | None) -> str:
    if config.URL_PUBLICA:
        return config.URL_PUBLICA
    return f'https://{dominio}' if dominio else ''


def previa(musica: dict) -> str:
    """Prévia (antes de pagar): o funil da música."""
    return f"{base(musica.get('dominio'))}/musica/p/{musica['token']}"


def presente(musica: dict) -> str:
    """Página do presente (QR code e e-mail para quem recebe): só a música, sem dados de quem comprou."""
    return f"{base(musica.get('dominio'))}/musica/m/{musica['token']}"


def compra(guid: str, dominio: str | None) -> str:
    """Área de quem comprou (pelo guid do pedido pago): fotos do videoclipe, QR, entrega por e-mail."""
    return f'{base(dominio)}/musica/compra/{guid}'


def webhook(nome_gerador: str) -> str | None:
    return f'{config.URL_PUBLICA}/musica/webhook/{nome_gerador}' if config.URL_PUBLICA else None
