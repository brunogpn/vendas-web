"""Apps das clientes (PWA em /app/<slug>/). Ver docs/APPS.md.

Para criar um app novo: pasta apps/<slug>/ com config.py (AppConfig) e rotas.py (um Blueprint
`bp` com url_prefix=/app/<slug>), migration com as tabelas app_<slug>_*, e incluir o módulo em
_MODULOS abaixo. Login, sessão, licença, PWA, avisos e a ligação com a venda vêm do _nucleo.
"""
import importlib
import logging

from apps._nucleo.config_base import AppConfig

# Módulos dos apps ativos (apps.<nome>).
_MODULOS = ['fatia']

APPS: dict[str, AppConfig] = {}
for _nome in _MODULOS:
    _cfg = importlib.import_module(f'apps.{_nome}.config').CONFIG
    APPS[_cfg.slug] = _cfg


def app_config(slug: str) -> AppConfig | None:
    return APPS.get(slug)


def apps_do_produto(produto_id) -> list[tuple[AppConfig, int]]:
    """Apps (e dias) que a compra de um produto libera: produto do tipo app (tabela apps_produto,
    cadastrada no admin em "E-books do produto")."""
    try:
        pid = int(produto_id)
    except (TypeError, ValueError):
        return []
    from database import get_app_produto
    linha = get_app_produto(pid)
    if not linha or linha['app_slug'] not in APPS:
        return []
    return [(APPS[linha['app_slug']], int(linha['dias']))]


def registrar(flask_app):
    """Registra o núcleo (login, PWA) e o blueprint de cada app.

    Um app com problema (ex.: erro de digitação num .txt de receita, que falha no import de
    propósito) fica fora do ar sozinho — nunca pode derrubar o resto do site."""
    from apps._nucleo.rotas import bp as nucleo_bp
    flask_app.register_blueprint(nucleo_bp)
    for nome in _MODULOS:
        try:
            flask_app.register_blueprint(importlib.import_module(f'apps.{nome}.rotas').bp)
        except Exception as e:
            logging.getLogger(__name__).error(f"[APPS] App '{nome}' NÃO carregado (fora do ar): {e}")
