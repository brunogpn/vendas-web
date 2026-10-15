"""Ligação entre os apps e a Estante 2 (/pedido2/<guid>): "Meus Apps" na Estante e "Meus e-books" no app."""
import logging

from database import db
from apps import APPS
from apps._nucleo import licenca as lic

logger = logging.getLogger(__name__)


def apps_da_estante(pedido: dict) -> tuple[list[dict], list[dict]]:
    """Para a Estante 2: ("Meus apps" da cliente do pedido, apps para oferecer no cross-sell).

    Uma busca só da cliente e das licenças para as duas seções (é a página de mais tráfego depois
    de uma venda). Ofertas = produtos do tipo app (não renovação, à venda no site, app público) de
    apps que ela ainda não tem, no mesmo formato dos e-books do cross-sell; um card por app: o produto
    principal (o mais caro), com o desconto de oferta quando houver."""
    from database import listar_apps_produto
    cliente = lic.buscar_cliente_por_email(pedido.get('email'))
    licencas = lic.listar_licencas_do_cliente(cliente['id']) if cliente else []
    produtos_app = listar_apps_produto()  # ordem: preço
    # Capa do app na Estante (mesmo formato dos livros): a "Imagem pequena" de um produto do app,
    # cadastrada no admin; sem nenhuma, o template usa o ícone do app (ver pedido-2.html).
    capas = {}
    for p in produtos_app:
        if p['imagem_pequena']:
            capas.setdefault(p['app_slug'], p['imagem_pequena'])
    meus = [{'app': APPS[l['app_slug']], 'licenca': l, 'ativa': lic.licenca_ativa(l), 'capa': capas.get(l['app_slug'])}
            for l in licencas if l['app_slug'] in APPS]
    tem = {l['app_slug'] for l in licencas}
    # Um card por app: o produto principal (o mais caro à venda, não renovação). Se ele tem desconto de
    # oferta (produtos.desconto_oferta, migration 083), o card mostra o preço com desconto e o link
    # leva o token da oferta (web/oferta.py) — o checkout aplica e grava o desconto.
    from web.oferta import aplicar_na_vitrine, descontos_dos_produtos
    principal_por_app = {}
    for p in produtos_app:  # ordem: preço → o último de cada app é o mais caro
        if (p['app_slug'] in APPS and APPS[p['app_slug']].publico and not p['renovacao'] and p['ativo']
                and p['disponivel_web'] and p['app_slug'] not in tem):
            principal_por_app[p['app_slug']] = p
    descontos = descontos_dos_produtos(p['produto_id'] for p in principal_por_app.values())
    ofertas = [aplicar_na_vitrine({'produto_id': p['produto_id'], 'ebook_id': None, 'nome_venda': p['nome_venda'],
                                   'imagem_pequena': p['imagem_pequena'] or capas.get(slug),
                                   'imagem_grande': p['imagem_grande'], 'preco_promocional': p['preco_promocional'],
                                   'app_slug': slug, 'icone_app': APPS[slug].icone_512}, descontos)
               for slug, p in principal_por_app.items()]
    return meus, ofertas


def pedido_da_estante(cliente: dict, slug: str):
    """Um pedido pago da cliente com guid, para abrir a Estante 2 a partir do app.

    Prefere o pedido que liberou o app; senão, o pedido pago mais recente com o mesmo e-mail.
    """
    linha = db.execute_query(
        "SELECT p.id, p.guid, p.email, p.contact_phone, p.estado_id, p.data_envio_pedido "
        "FROM apps_licenca_pedidos lp JOIN pedidos p ON p.id = lp.pedido_id "
        "WHERE lp.cliente_id = %s AND lp.app_slug = %s AND p.guid IS NOT NULL "
        "ORDER BY lp.criado_em DESC LIMIT 1", (cliente['id'], slug), fetch_one=True)
    if linha:
        return linha
    return db.execute_query(
        "SELECT id, guid, email, contact_phone, estado_id, data_envio_pedido FROM pedidos "
        "WHERE email = %s AND estado_id IN (0, 1000) AND guid IS NOT NULL "
        "ORDER BY id DESC LIMIT 1", (cliente['email'],), fetch_one=True)


def ebooks_da_cliente(cliente: dict, slug: str) -> tuple[str | None, list[dict]]:
    """(guid da estante, e-books liberados) — os mesmos que a Estante 2 mostra."""
    from web.checkout import resolver_pedido_por_guid, listar_itens_ebook_do_cliente
    ref = pedido_da_estante(cliente, slug)
    if not ref:
        return None, []
    pedido, _, erro = resolver_pedido_por_guid(ref['guid'])
    if erro:
        return None, []
    try:
        itens = [i for i in listar_itens_ebook_do_cliente(pedido) if not i.get('bloqueado')]
    except Exception as e:
        logger.error(f"[APPS] Erro ao listar e-books da cliente #{cliente['id']}: {e}")
        itens = []
    return pedido['guid'], itens

