"""Clientes e licenças dos apps.

Regra da licença (igual ao app original do Bruno):
- ativa enquanto expira_em >= hoje (o dia do vencimento ainda vale);
- comprar/renovar ANTES de vencer soma os dias a partir do vencimento atual; DEPOIS de vencer,
  a partir de hoje;
- o mesmo pedido nunca soma duas vezes (PK de apps_licenca_pedidos).

Vencida, a cliente continua entrando e vendo tudo, mas não grava nada novo (decorators em auth.py).
"""
import datetime
import logging

from database import db
from apps import APPS, apps_do_pedido
from apps._nucleo import datas

logger = logging.getLogger(__name__)

# Só venda pelo site libera app: no WhatsApp a entrega vem antes do pagamento (estado 0 nem
# sempre é "pagou" no sentido do checkout), e produto de app é vendido só no site.
ESTADO_PAGO_WEB = 1000


def normalizar_email(email) -> str:
    return (email or '').strip().lower()


# ---------------------------------------------------------------- clientes

def buscar_cliente(cliente_id):
    return db.execute_query(
        "SELECT id, email, nome, criado_em FROM apps_clientes WHERE id = %s", (cliente_id,), fetch_one=True)


def buscar_cliente_por_email(email):
    email = normalizar_email(email)
    if not email:
        return None
    return db.execute_query(
        "SELECT id, email, nome, criado_em FROM apps_clientes WHERE email = %s", (email,), fetch_one=True)


def _obter_ou_criar_cliente(cursor, email: str, nome: str | None) -> int:
    # LAST_INSERT_ID(id) devolve o id da linha existente quando o e-mail já está cadastrado.
    cursor.execute(
        "INSERT INTO apps_clientes (email, nome) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id), nome = COALESCE(nome, VALUES(nome))",
        (email, nome),
    )
    return cursor.lastrowid


def obter_ou_criar_cliente(email, nome=None) -> int:
    email = normalizar_email(email)
    if not email:
        raise ValueError('e-mail vazio')
    with db.get_cursor() as cursor:
        return _obter_ou_criar_cliente(cursor, email, (nome or '').strip()[:120] or None)


def trocar_email(cliente_id: int, novo_email: str, usuario_admin: str | None = None) -> str | None:
    """Troca o e-mail de acesso. Devolve uma mensagem de erro, ou None se deu certo."""
    novo = normalizar_email(novo_email)
    if '@' not in novo or '.' not in novo.split('@')[-1]:
        return 'E-mail inválido.'
    outro = buscar_cliente_por_email(novo)
    if outro and outro['id'] != cliente_id:
        return f'Já existe outra cliente com o e-mail {novo} (id {outro["id"]}).'
    atual = buscar_cliente(cliente_id)
    if not atual:
        return 'Cliente não encontrada.'
    with db.get_cursor() as cursor:
        cursor.execute("UPDATE apps_clientes SET email = %s WHERE id = %s", (novo, cliente_id))
        # Sessões continuam valendo (são do cliente, não do e-mail); o código pendente do e-mail antigo cai fora.
        cursor.execute("DELETE FROM apps_codigos_login WHERE email = %s", (atual['email'],))
        cursor.execute(
            "INSERT INTO apps_licenca_ajustes (cliente_id, app_slug, acao, detalhe, usuario_admin) "
            "VALUES (%s, '', 'trocar_email', %s, %s)",
            (cliente_id, f"{atual['email']} → {novo}", usuario_admin),
        )
    return None


# ---------------------------------------------------------------- licenças

def buscar_licenca(cliente_id: int, slug: str):
    return db.execute_query(
        "SELECT id, cliente_id, app_slug, expira_em, ultimo_acesso_em, criado_em "
        "FROM apps_licencas WHERE cliente_id = %s AND app_slug = %s",
        (cliente_id, slug), fetch_one=True)


def listar_licencas_do_cliente(cliente_id: int) -> list[dict]:
    return db.execute_query(
        "SELECT id, app_slug, expira_em, ultimo_acesso_em, criado_em FROM apps_licencas "
        "WHERE cliente_id = %s ORDER BY app_slug", (cliente_id,), fetch_all=True) or []


def licenca_ativa(licenca) -> bool:
    return bool(licenca) and datas.como_data(licenca['expira_em']) >= datas.hoje()


def dias_restantes(licenca) -> int | None:
    """Dias até o vencimento (0 = vence hoje, negativo = venceu). None sem licença."""
    if not licenca:
        return None
    return datas.dias_entre(datas.hoje(), licenca['expira_em'])


def nova_expiracao(expira_atual, dias: int, hoje: datetime.date | None = None) -> datetime.date:
    hoje = hoje or datas.hoje()
    atual = datas.como_data(expira_atual)
    base = atual if atual and atual >= hoje else hoje
    return base + datetime.timedelta(days=dias)


def _somar_dias(cursor, cliente_id: int, slug: str, dias: int):
    """Soma dias na licença (cria se não existe). Devolve (expira_antes, expira_depois)."""
    cursor.execute(
        "SELECT id, expira_em FROM apps_licencas WHERE cliente_id = %s AND app_slug = %s FOR UPDATE",
        (cliente_id, slug))
    linha = cursor.fetchone()
    antes = linha['expira_em'] if linha else None
    depois = nova_expiracao(antes, dias)
    if linha:
        cursor.execute("UPDATE apps_licencas SET expira_em = %s WHERE id = %s", (depois, linha['id']))
    else:
        cursor.execute(
            "INSERT INTO apps_licencas (cliente_id, app_slug, expira_em) VALUES (%s, %s, %s)",
            (cliente_id, slug, depois))
    return antes, depois


def liberar_licencas_do_pedido(pedido_id: int) -> list[dict]:
    """Libera (ou soma dias) os apps que o pedido comprou (itens app do plano — ver apps_do_pedido). Idempotente.

    Chamada no início da entrega por e-mail (tasks.enviar_email_entrega) — por onde passam todos os
    caminhos que confirmam pagamento web — e de novo na rota "abrir app" da Estante, para não
    depender da fila do Celery logo depois do pagamento. Devolve o que foi liberado AGORA.
    """
    pedido = db.execute_query(
        "SELECT id, produto_id, email, contact_name, estado_id, valor_pago FROM pedidos WHERE id = %s",
        (pedido_id,), fetch_one=True)
    if not pedido or pedido['estado_id'] != ESTADO_PAGO_WEB:
        return []
    apps = apps_do_pedido(pedido_id)
    if not apps:
        return []
    email = normalizar_email(pedido.get('email'))
    if not email:
        logger.warning(f"[APPS] Pedido #{pedido_id} pago libera app, mas não tem e-mail — licença não criada")
        return []

    liberadas = []
    for cfg, dias in apps:
        with db.get_cursor() as cursor:
            cliente_id = _obter_ou_criar_cliente(cursor, email, (pedido.get('contact_name') or '').strip()[:120] or None)
            # Trava de idempotência: quem conseguir inserir a linha do pedido é quem soma os dias.
            # Uma segunda chamada simultânea espera o commit desta e recebe rowcount 0.
            cursor.execute(
                "INSERT IGNORE INTO apps_licenca_pedidos "
                "(pedido_id, app_slug, cliente_id, produto_id, dias, valor, expira_depois) "
                "VALUES (%s, %s, %s, %s, %s, %s, CURDATE())",
                (pedido_id, cfg.slug, cliente_id, pedido['produto_id'], dias, pedido.get('valor_pago')))
            if cursor.rowcount == 0:
                continue
            antes, depois = _somar_dias(cursor, cliente_id, cfg.slug, dias)
            cursor.execute(
                "UPDATE apps_licenca_pedidos SET expira_antes = %s, expira_depois = %s "
                "WHERE pedido_id = %s AND app_slug = %s",
                (antes, depois, pedido_id, cfg.slug))
        logger.info(f"[APPS] Pedido #{pedido_id}: {cfg.slug} +{dias} dias para cliente #{cliente_id} ({antes} → {depois})")
        liberadas.append({'app_slug': cfg.slug, 'cliente_id': cliente_id, 'dias': dias, 'expira_em': depois})
    return liberadas


def pedido_criou_a_conta(cliente_id: int, pedido_id: int, slug: str) -> bool:
    """True se este pedido foi o que CRIOU a conta da cliente: liberou a primeira licença dela (neste
    app, sem licença anterior), ela não tem licença de outro app nem ajuste manual.

    É a condição para entrar no app SEM código a partir da Estante/checkout: o e-mail digitado no
    checkout não é verificado, então quem compra com o e-mail de outra pessoa não pode, por esse
    caminho, entrar numa conta que já existia (com vendas, metas, perfil). Conta já existente =
    login pelo código enviado ao e-mail."""
    linha = db.execute_query(
        "SELECT expira_antes FROM apps_licenca_pedidos WHERE pedido_id = %s AND app_slug = %s AND cliente_id = %s",
        (pedido_id, slug, cliente_id), fetch_one=True)
    if not linha or linha['expira_antes'] is not None:
        return False
    outros = db.execute_query(
        "SELECT (SELECT COUNT(*) FROM apps_licencas WHERE cliente_id = %s AND app_slug <> %s) AS licencas, "
        "       (SELECT COUNT(*) FROM apps_licenca_pedidos WHERE cliente_id = %s AND pedido_id <> %s) AS pedidos, "
        "       (SELECT COUNT(*) FROM apps_licenca_ajustes WHERE cliente_id = %s) AS ajustes",
        (cliente_id, slug, cliente_id, pedido_id, cliente_id), fetch_one=True)
    return not (outros['licencas'] or outros['pedidos'] or outros['ajustes'])


def reconciliar_licencas(dias: int = 7) -> int:
    """Rede de segurança (Celery, de hora em hora): pedidos pagos nos últimos `dias` com item app que
    ainda não liberaram. Devolve quantas licenças liberou."""
    pendentes = db.execute_query(
        "SELECT DISTINCT p.id FROM pedidos p JOIN pedido_itens pi ON pi.pedido_id = p.id AND pi.app_slug IS NOT NULL "
        "WHERE p.estado_id = 1000 AND p.data_pagamento >= DATE_SUB(NOW(), INTERVAL %s DAY) "
        "AND NOT EXISTS (SELECT 1 FROM apps_licenca_pedidos lp WHERE lp.pedido_id = p.id)",
        (dias,), fetch_all=True) or []
    total = 0
    for linha in pendentes:
        try:
            total += len(liberar_licencas_do_pedido(linha['id']))
        except Exception as e:
            logger.error(f"[APPS] Reconciliação: erro no pedido #{linha['id']}: {e}")
    return total


def ajustar_licenca(cliente_id: int, slug: str, *, dias: int | None = None, nova_data=None,
                    usuario_admin: str | None = None) -> datetime.date:
    """Ajuste manual do admin: soma `dias` (regra normal) ou define `nova_data`. Cria a licença se faltar."""
    if slug not in APPS:
        raise ValueError(f'app desconhecido: {slug}')
    with db.get_cursor() as cursor:
        if nova_data is not None:
            nova = datas.como_data(nova_data)
            cursor.execute(
                "INSERT INTO apps_licencas (cliente_id, app_slug, expira_em) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE expira_em = VALUES(expira_em)", (cliente_id, slug, nova))
            detalhe = f'vencimento definido para {nova.isoformat()}'
        else:
            _, nova = _somar_dias(cursor, cliente_id, slug, int(dias))
            detalhe = f'{int(dias):+d} dias → {nova.isoformat()}'
        cursor.execute(
            "INSERT INTO apps_licenca_ajustes (cliente_id, app_slug, acao, detalhe, usuario_admin) "
            "VALUES (%s, %s, 'estender', %s, %s)", (cliente_id, slug, detalhe, usuario_admin))
    return nova


def pedidos_da_licenca(cliente_id: int, slug: str) -> list[dict]:
    return db.execute_query(
        "SELECT lp.pedido_id, lp.produto_id, lp.dias, lp.valor, lp.expira_antes, lp.expira_depois, lp.criado_em, "
        "p.guid FROM apps_licenca_pedidos lp JOIN pedidos p ON p.id = lp.pedido_id "
        "WHERE lp.cliente_id = %s AND lp.app_slug = %s ORDER BY lp.criado_em DESC",
        (cliente_id, slug), fetch_all=True) or []


def registrar_acesso(cliente_id: int, slug: str) -> None:
    """Marca que a cliente abriu o app hoje (uma escrita por dia, no máximo)."""
    with db.get_cursor() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO apps_acessos_dia (cliente_id, app_slug, data) VALUES (%s, %s, CURDATE())",
            (cliente_id, slug))
        if cursor.rowcount:
            cursor.execute(
                "UPDATE apps_licencas SET ultimo_acesso_em = NOW() WHERE cliente_id = %s AND app_slug = %s",
                (cliente_id, slug))
