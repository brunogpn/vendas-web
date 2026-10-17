"""Admin dos apps das clientes (App Fatias etc.): busca de cliente, licença, ajustes e link de acesso.

Usado pelo atendimento ("paguei e não consigo entrar", "comprei com outro e-mail", "meu acesso
venceu") e para criar clientes de teste no dev. Ver docs/APPS.md.
"""
import datetime
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


POR_PAGINA = 50
SITUACOES = {
    'ativa': 'l.expira_em >= CURDATE()',
    'vencida': 'l.expira_em < CURDATE()',
    'vence7': 'l.expira_em BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)',
}


def _resumo_por_app():
    """Números do topo, por app. Contas pelos índices (app_slug, expira_em) e (app_slug, data) — sem
    subconsulta por licença, que pesaria com dezenas de milhares de clientes."""
    linhas = db.execute_query(
        "SELECT app_slug, COUNT(*) AS total, SUM(expira_em >= CURDATE()) AS ativas, "
        "SUM(ultimo_acesso_em IS NOT NULL) AS entraram FROM apps_licencas GROUP BY app_slug",
        fetch_all=True) or []
    resumo = {l['app_slug']: dict(l) for l in linhas}
    for l in db.execute_query(
            "SELECT app_slug, COUNT(DISTINCT cliente_id) AS ativas_7d FROM apps_acessos_dia "
            "WHERE data >= DATE_SUB(CURDATE(), INTERVAL 6 DAY) GROUP BY app_slug", fetch_all=True) or []:
        resumo.setdefault(l['app_slug'], {})['ativas_7d'] = l['ativas_7d']
    return resumo


def _data(valor, padrao):
    try:
        return datetime.date.fromisoformat(valor) if valor else padrao
    except ValueError:
        return padrao


@admin_bp.route('/apps')
@requer_admin
def apps_clientes():
    """Busca pelo começo do e-mail ou do nome (sem período, pelos índices) ou lista paginada por app e:
    situação (ativa / vence em 7 dias / vencida — pelo vencimento, sem período) ou, em "Todas", o período
    em que o app foi liberado pela primeira vez."""
    apps = _apps()
    q = (request.args.get('q') or '').strip().lower()
    hoje = datetime.date.today()
    filtro = {
        'app': request.args.get('app') if request.args.get('app') in apps else next(iter(apps), ''),
        'de': _data(request.args.get('de'), hoje - datetime.timedelta(days=30)),
        'ate': _data(request.args.get('ate'), hoje),
        'situacao': request.args.get('situacao') if request.args.get('situacao') in SITUACOES else '',
    }
    pagina = max(1, request.args.get('pagina', 1, type=int))
    linhas, tem_mais, resumo, erro_tabela = [], False, {}, None
    try:
        if q:
            prefixo = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            # Duas buscas por índice (e-mail único; nome — migration 088) em vez de um OR, que leria a tabela.
            linhas = db.execute_query(
                "SELECT c.id, c.email, c.nome, l.app_slug, l.expira_em, l.ultimo_acesso_em, l.criado_em "
                "FROM (SELECT id FROM apps_clientes WHERE email LIKE %s "
                "      UNION SELECT id FROM apps_clientes WHERE nome LIKE %s LIMIT 50) achados "
                "JOIN apps_clientes c ON c.id = achados.id "
                "LEFT JOIN apps_licencas l ON l.cliente_id = c.id ORDER BY c.email",
                (prefixo, prefixo), fetch_all=True) or []
        else:
            sql = ("SELECT c.id, c.email, c.nome, l.app_slug, l.expira_em, l.ultimo_acesso_em, l.criado_em "
                   "FROM apps_licencas l JOIN apps_clientes c ON c.id = l.cliente_id WHERE l.app_slug = %s")
            params = [filtro['app']]
            if filtro['situacao']:
                # Pelo vencimento (índice app_slug, expira_em): quem vence esta semana liberou há ~3 meses,
                # fora de qualquer período "recente" — combinar os dois esconderia justamente essas clientes.
                sql += ' AND ' + SITUACOES[filtro['situacao']] + ' ORDER BY l.expira_em'
            else:
                sql += (" AND l.criado_em >= %s AND l.criado_em < DATE_ADD(%s, INTERVAL 1 DAY)"
                        " ORDER BY l.criado_em DESC")
                params += [filtro['de'], filtro['ate']]
            linhas = db.execute_query(sql + ' LIMIT %s OFFSET %s',
                                      (*params, POR_PAGINA + 1, (pagina - 1) * POR_PAGINA), fetch_all=True) or []
            tem_mais = len(linhas) > POR_PAGINA
            linhas = linhas[:POR_PAGINA]
        resumo = _resumo_por_app()
    except Exception as e:  # migration 080 ainda não aplicada
        logger.error(f"[ADMIN-APPS] {e}")
        erro_tabela = str(e)
    return render_template('admin/apps_clientes.html', linhas=linhas, q=q, filtro=filtro, pagina=pagina,
                           tem_mais=tem_mais, situacoes=SITUACOES, apps=apps, resumo=resumo,
                           erro_tabela=erro_tabela)


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
