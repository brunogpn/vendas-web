"""Endereços dos apps.

Cada app tem um domínio oficial (config.dominio): o ícone instalado e o cookie de sessão ficam
presos ao domínio, então links que saem do sistema (Estante em outro domínio, e-mails) apontam
sempre para ele. Sem domínio configurado (dev), usa APP_BASE_URL ou o mesmo host da requisição.
"""
import os


def base_absoluta(cfg) -> str:
    if cfg.dominio:
        return f'https://{cfg.dominio}'
    return (os.getenv('APP_BASE_URL') or '').rstrip('/')


def url_absoluta(cfg, caminho: str = '') -> str:
    return f'{base_absoluta(cfg)}{cfg.prefixo}{caminho}'
