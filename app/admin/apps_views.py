"""Admin dos apps das clientes (App Fatias etc.): busca de cliente, licença, ajustes e link de acesso.

Usado pelo atendimento ("paguei e não consigo entrar", "comprei com outro e-mail", "meu acesso
venceu") e para criar clientes de teste no dev. Ver docs/APPS.md.
"""
import logging

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from admin import admin_bp
from admin.auth import requer_admin
from database import db

logger = logging.getLogger(__name__)

LINK_ADMIN_MINUTOS = 72 * 60  # link mandado pelo atendimento: vale 3 dias, uso único


def _apps():
    from apps import APPS
    return APPS


def _resumo_por_app():
    linhas = db.execute_query(
        "SELECT l.app_slug, COUNT(*) AS total, SUM(l.expira_em >= CURDATE()) AS ativas, "
        "SUM(l.ultimo_acesso_em IS NOT NULL) AS entraram, "
        "SUM(EXISTS (SELECT 1 FROM apps_acessos_dia a WHERE a.cliente_id = l.cliente_id AND a.app_slug = l.app_slug "
        "            AND a.data >= DATE_SUB(CURDATE(), INTERVAL 6 DAY))) AS ativas_7d "
        "FROM apps_licencas l GROUP BY l.app_slug", fetch_all=True) or []
    return {l['app_slug']: l for l in linhas}


@admin_bp.route('/apps')
@requer_admin
def apps_clientes():
    q = (request.args.get('q') or '').strip().lower()
    try:
        if q:
            clientes = db.execute_query(
                "SELECT c.id, c.email, c.nome, c.criado_em FROM apps_clientes c "
                "WHERE c.email LIKE %s OR c.nome LIKE %s ORDER BY c.id DESC LIMIT 50",
                (f'%{q}%', f'%{q}%'), fetch_all=True) or []
        else:
            clientes = db.execute_query(
                "SELECT c.id, c.email, c.nome, c.criado_em FROM apps_clientes c ORDER BY c.id DESC LIMIT 50",
                fetch_all=True) or []
        licencas = {}
        if clientes:
            ids = [c['id'] for c in clientes]
            marcas = ', '.join(['%s'] * len(ids))
            for l in db.execute_query(
                    f"SELECT cliente_id, app_slug, expira_em, ultimo_acesso_em FROM apps_licencas WHERE cliente_id IN ({marcas})",
                    tuple(ids), fetch_all=True) or []:
                licencas.setdefault(l['cliente_id'], []).append(l)
        resumo = _resumo_por_app()
        erro_tabela = None
    except Exception as e:  # migration 080 ainda não aplicada
        logger.error(f"[ADMIN-APPS] {e}")
        clientes, licencas, resumo, erro_tabela = [], {}, {}, str(e)
    return render_template('admin/apps_clientes.html', clientes=clientes, licencas=licencas, q=q,
                           apps=_apps(), resumo=resumo, erro_tabela=erro_tabela)


@admin_bp.route('/apps/cliente/<int:cliente_id>')
@requer_admin
def apps_cliente(cliente_id):
    from apps._nucleo import licenca as lic
    cliente = lic.buscar_cliente(cliente_id)
    if not cliente:
        flash('Cliente não encontrada.', 'danger')
        return redirect(url_for('admin.apps_clientes'))
    licencas = []
    for l in lic.listar_licencas_do_cliente(cliente_id):
        licencas.append({**l, 'ativa': lic.licenca_ativa(l), 'dias': lic.dias_restantes(l),
                         'pedidos': lic.pedidos_da_licenca(cliente_id, l['app_slug']),
                         'app': _apps().get(l['app_slug'])})
    ajustes = db.execute_query(
        "SELECT app_slug, acao, detalhe, usuario_admin, criado_em FROM apps_licenca_ajustes "
        "WHERE cliente_id = %s ORDER BY id DESC LIMIT 30", (cliente_id,), fetch_all=True) or []
    pedidos_email = db.execute_query(
        "SELECT id, produto_id, estado_id, valor_pago, data_pagamento, guid FROM pedidos "
        "WHERE email = %s ORDER BY id DESC LIMIT 20", (cliente['email'],), fetch_all=True) or []
    # Link gerado agora (ver apps_gerar_link): vem pela sessão, mostrado uma vez só — nunca na URL.
    gerado = session.pop('apps_link_gerado', None)
    link = gerado['link'] if gerado and gerado.get('cliente_id') == cliente_id else None
    return render_template('admin/apps_cliente.html', cliente=cliente, licencas=licencas, ajustes=ajustes,
                           pedidos_email=pedidos_email, apps=_apps(), link=link)


@admin_bp.route('/apps/cliente/criar', methods=['POST'])
@requer_admin
def apps_criar_cliente():
    from apps._nucleo import licenca as lic
    email = lic.normalizar_email(request.form.get('email'))
    slug = request.form.get('app_slug') or ''
    try:
        dias = int(request.form.get('dias') or 0)
    except ValueError:
        dias = 0
    if '@' not in email or slug not in _apps() or dias <= 0:
        flash('Preencha e-mail, app e dias (maior que zero).', 'danger')
        return redirect(url_for('admin.apps_clientes'))
    cliente_id = lic.obter_ou_criar_cliente(email, request.form.get('nome'))
    nova = lic.ajustar_licenca(cliente_id, slug, dias=dias, usuario_admin=current_user.email)
    flash(f'Acesso ao {_apps()[slug].nome} liberado para {email} até {nova.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))


@admin_bp.route('/apps/cliente/<int:cliente_id>/ajustar', methods=['POST'])
@requer_admin
def apps_ajustar_licenca(cliente_id):
    from apps._nucleo import licenca as lic
    slug = request.form.get('app_slug') or ''
    if slug not in _apps():
        flash('App inválido.', 'danger')
        return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))
    data = (request.form.get('nova_data') or '').strip()
    try:
        if data:
            nova = lic.ajustar_licenca(cliente_id, slug, nova_data=data, usuario_admin=current_user.email)
        else:
            nova = lic.ajustar_licenca(cliente_id, slug, dias=int(request.form.get('dias') or 0),
                                       usuario_admin=current_user.email)
        flash(f'Novo vencimento: {nova.strftime("%d/%m/%Y")}.', 'success')
    except ValueError:
        flash('Informe os dias (número) ou uma data válida.', 'danger')
    return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))


@admin_bp.route('/apps/cliente/<int:cliente_id>/email', methods=['POST'])
@requer_admin
def apps_trocar_email(cliente_id):
    from apps._nucleo import licenca as lic
    erro = lic.trocar_email(cliente_id, request.form.get('novo_email'), usuario_admin=current_user.email)
    flash(erro or 'E-mail de acesso trocado.', 'danger' if erro else 'success')
    return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))


@admin_bp.route('/apps/cliente/<int:cliente_id>/link', methods=['POST'])
@requer_admin
def apps_gerar_link(cliente_id):
    """Link de entrada sem código (uso único, 3 dias) para o atendimento mandar à cliente."""
    from apps._nucleo import auth, licenca as lic
    from apps._nucleo.urls import base_absoluta, url_absoluta
    slug = request.form.get('app_slug') or ''
    cfg = _apps().get(slug)
    if not cfg or not lic.buscar_licenca(cliente_id, slug):
        flash('Essa cliente não tem licença desse app.', 'danger')
        return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))
    token = auth.criar_link_entrada(cliente_id, slug, minutos=LINK_ADMIN_MINUTOS)
    import config
    caminho = f'/entrar/link/{token}'
    if (cfg.dominio or config.EH_PRODUCAO) and base_absoluta(cfg):
        link = url_absoluta(cfg, caminho)
    else:  # dev: o APP_BASE_URL aponta para o site real
        link = request.host_url.rstrip('/') + cfg.prefixo + caminho
    db.execute_query(
        "INSERT INTO apps_licenca_ajustes (cliente_id, app_slug, acao, detalhe, usuario_admin) "
        "VALUES (%s, %s, 'link_acesso', 'link de 3 dias gerado', %s)", (cliente_id, slug, current_user.email))
    # Pela sessão, não pela URL: na URL o token (entra sem código por 3 dias) ficaria no log do nginx
    # e no histórico do navegador.
    session['apps_link_gerado'] = {'cliente_id': cliente_id, 'link': link}
    return redirect(url_for('admin.apps_cliente', cliente_id=cliente_id))


# ---------------------------------------------------------------- produto do tipo app

@admin_bp.route('/produto/<int:produto_id>/app', methods=['POST'])
@requer_admin
def salvar_app_produto_view(produto_id):
    """Marca o produto como "app" (apps_produto): o app vira o item principal do checkout."""
    from database import get_ebook_principal_produto, get_app_produto, salvar_app_produto
    destino = redirect(url_for('admin.produto_ebooks', produto_id=produto_id))
    if db.execute_query("SELECT 1 FROM telefones_produto WHERE produto_id = %s LIMIT 1", (produto_id,), fetch_one=True):
        flash('Este produto tem número de WhatsApp: produto de app é vendido só no site (no WhatsApp a '
              'entrega vem antes do pagamento). Use um produto só do site.', 'warning')
        return destino
    principal = get_ebook_principal_produto(produto_id)
    if principal and not get_app_produto(produto_id):
        flash('Este produto já tem um e-book principal. Remova-o antes de transformar o produto em app.', 'warning')
        return destino
    f = request.form
    slug = f.get('app_slug') or ''
    try:
        dias = int(f.get('dias') or 0)
        preco_original = float(f.get('preco_original') or 0)
        preco = float(f.get('preco_promocional') or 0)
    except ValueError:
        flash('Dias e preços precisam ser números.', 'warning')
        return destino
    nome = (f.get('nome_venda') or '').strip()
    if slug not in _apps() or dias <= 0 or preco <= 0 or not nome:
        flash('Preencha app, dias (> 0), nome de venda e preço cobrado (> 0).', 'warning')
        return destino
    salvar_app_produto(produto_id, slug, dias, bool(f.get('renovacao')), nome, (f.get('descricao') or '').strip(),
                       (f.get('imagem_grande') or '').strip(), (f.get('imagem_pequena') or '').strip(),
                       max(preco_original, preco), preco)
    logger.info(f"[ADMIN-APPS] Produto #{produto_id} → app {slug} ({dias} dias, R$ {preco:.2f}) por {current_user.email}")
    flash(f'Produto salvo como app: {nome} — {dias} dias por R$ {preco:.2f}.', 'success')
    return destino


@admin_bp.route('/produto/<int:produto_id>/app/remover', methods=['POST'])
@requer_admin
def remover_app_produto_view(produto_id):
    from database import remover_app_produto
    if remover_app_produto(produto_id):
        logger.info(f"[ADMIN-APPS] Produto #{produto_id} deixou de ser app por {current_user.email}")
        flash('O produto deixou de ser app. Licenças já vendidas continuam valendo.', 'success')
    return redirect(url_for('admin.produto_ebooks', produto_id=produto_id))


# ---------------------------------------------------------------- desconto de oferta (popup / Estante)

@admin_bp.route('/produto/<int:produto_id>/desconto-oferta', methods=['POST'])
@requer_admin
def salvar_desconto_oferta(produto_id):
    """produtos.desconto_oferta (migration 083): vale para app e e-book; precisa ser menor que o preço."""
    from database import get_ebook_principal_produto
    destino = redirect(url_for('admin.produto_ebooks', produto_id=produto_id))
    import math
    try:
        desconto = float((request.form.get('desconto_oferta') or '0').replace(',', '.'))
        if not math.isfinite(desconto):
            raise ValueError
        desconto = round(desconto, 2)
    except ValueError:
        flash('O desconto precisa ser um número.', 'warning')
        return destino
    principal = get_ebook_principal_produto(produto_id)
    preco = float(principal['preco_promocional']) if principal else 0.0
    if desconto < 0 or (desconto > 0 and desconto >= preco):
        flash(f'O desconto precisa ser maior ou igual a zero e menor que o preço (R$ {preco:.2f}).', 'warning')
        return destino
    db.execute_query("UPDATE produtos SET desconto_oferta = %s WHERE id = %s", (desconto, produto_id))
    logger.info(f"[ADMIN-OFERTA] Produto #{produto_id}: desconto de oferta R$ {desconto:.2f} por {current_user.email}")
    flash(f'Desconto de oferta salvo: R$ {desconto:.2f} (sai por R$ {preco - desconto:.2f}).' if desconto
          else 'Oferta desligada (sem desconto).', 'success')
    return destino
