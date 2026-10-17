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


def apps_do_pedido(pedido_id) -> list[tuple[AppConfig, int]]:
    """Apps (e dias de acesso) que um pedido libera: os itens app gravados no pedido (pedido_itens.app_slug,
    vindos do plano comprado) com os dias do item no plano (plano_entregaveis.dias). O mesmo app duas vezes
    no pedido conta uma vez, com o maior prazo. App que não está em APPS (desligado) fica de fora.

    Item app sem o item do plano (ebook_produto_id NULL — gravado pelo código antigo na janela do deploy da
    migration 085) usa os dias do app no plano padrão do produto: a licença não pode depender da hora do deploy."""
    from database import db
    linhas = db.execute_query(
        """SELECT pi.app_slug,
                  MAX(COALESCE(pe.dias, (
                      SELECT MAX(pe2.dias) FROM plano_entregaveis pe2
                      JOIN produto_planos pp2 ON pp2.id = pe2.plano_id AND pp2.padrao = 1
                      JOIN entregaveis e2 ON e2.id = pe2.entregavel_id AND e2.tipo = 'app' AND e2.app_slug = pi.app_slug
                      WHERE pe2.produto_id = p.produto_id))) AS dias
           FROM pedido_itens pi
           JOIN pedidos p ON p.id = pi.pedido_id
           LEFT JOIN plano_entregaveis pe ON pe.id = pi.ebook_produto_id
           WHERE pi.pedido_id = %s AND pi.app_slug IS NOT NULL
           GROUP BY pi.app_slug""",
        (pedido_id,), fetch_all=True) or []
    return [(APPS[l['app_slug']], int(l['dias'])) for l in linhas if l['app_slug'] in APPS and l['dias']]


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
