"""Login dos apps: código de 6 números no e-mail, sessão por cookie e link de entrada de uso único.

Regras (as do app original, com o limite por IP a mais):
- só entra quem já é cliente (a conta nasce na compra ou pelo admin — não há cadastro aberto);
- código vale 15 min, aceita 5 tentativas; pedir de novo substitui o anterior;
- no máximo 5 códigos por e-mail e 20 por IP por hora (sem limite, dava para ir chutando códigos);
- sessão de 90 dias em cookie httpOnly; no banco só ficam hashes (código, sessão, link).

Rotas JSON devolvem `jsonify(...), 4xx` — nunca abort(): o handler global transforma em 500.
"""
import datetime
import hashlib
import hmac
import logging
import os
import re
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import g, jsonify, redirect, request

import config
from database import db
from apps._nucleo import datas, licenca as lic

logger = logging.getLogger(__name__)

COOKIE = 'apps_sessao'
COOKIE_PATH = '/app/'
SESSAO_DIAS = 90
CODIGO_MINUTOS = 15
MAX_TENTATIVAS = 5
MAX_CODIGOS_HORA_EMAIL = 5
MAX_CODIGOS_HORA_IP = 20
LINK_MINUTOS_PADRAO = 10

MSG_LICENCA_VENCIDA = 'Seu acesso venceu. Renove para continuar registrando seu progresso.'

_EMAIL_OK = re.compile(r'^\S+@\S+\.\S+$')


def _segredo() -> bytes:
    return (os.getenv('SECRET_KEY') or 'troque-em-producao').encode()


def _hash(texto: str) -> str:
    # HMAC com a SECRET_KEY: um vazamento só da tabela não permite testar códigos offline.
    return hmac.new(_segredo(), texto.encode(), hashlib.sha256).hexdigest()


def ip_cliente() -> str | None:
    # Sem ProxyFix no projeto: o IP real vem do nginx em X-Real-IP.
    return (request.headers.get('X-Real-IP') or request.remote_addr or '')[:45] or None


# ---------------------------------------------------------------- código por e-mail

def pedir_codigo(email: str, ip: str | None) -> dict:
    """Gera o código e devolve {'ok': True, 'cliente': ..., 'codigo': ...} ou {'ok': False, 'erro': ...}.
    Quem chama envia o e-mail (em dev, mostra o código na tela)."""
    email = lic.normalizar_email(email)
    if not _EMAIL_OK.match(email):
        return {'ok': False, 'erro': 'Esse email parece incompleto. Confira e tente de novo.'}
    cliente = lic.buscar_cliente_por_email(email)
    if not cliente:
        return {'ok': False, 'erro': 'Não encontramos uma compra com esse email. Use o mesmo email da compra.'}

    agora = datas.agora()
    uma_hora = agora - datetime.timedelta(hours=1)
    contagem = db.execute_query(
        "SELECT SUM(email = %s) AS por_email, SUM(ip = %s) AS por_ip "
        "FROM apps_pedidos_codigo WHERE criado_em > %s AND (email = %s OR ip = %s)",
        (email, ip, uma_hora, email, ip), fetch_one=True) or {}
    if int(contagem.get('por_email') or 0) >= MAX_CODIGOS_HORA_EMAIL:
        return {'ok': False, 'erro': 'Você já pediu vários códigos. Espere uma hora e tente de novo, '
                                     'ou use o último código que chegou no seu email.'}
    if ip and int(contagem.get('por_ip') or 0) >= MAX_CODIGOS_HORA_IP:
        return {'ok': False, 'erro': 'Muitos pedidos de código deste aparelho. Espere uma hora e tente de novo.'}

    codigo = f'{secrets.randbelow(1_000_000):06d}'
    with db.get_cursor() as cursor:
        cursor.execute("INSERT INTO apps_pedidos_codigo (email, ip, criado_em) VALUES (%s, %s, %s)",
                       (email, ip, agora))
        cursor.execute(
            "INSERT INTO apps_codigos_login (email, codigo_hash, expira_em, tentativas) VALUES (%s, %s, %s, 0) "
            "ON DUPLICATE KEY UPDATE codigo_hash = VALUES(codigo_hash), expira_em = VALUES(expira_em), tentativas = 0",
            (email, _hash(f'codigo:{email}:{codigo}'), agora + datetime.timedelta(minutes=CODIGO_MINUTOS)))
    return {'ok': True, 'cliente': cliente, 'codigo': codigo}


def confirmar_codigo(email: str, codigo: str) -> tuple[int | None, str | None]:
    """Devolve (cliente_id, None) se o código confere, ou (None, mensagem de erro).

    A tentativa é RESERVADA antes de conferir, num UPDATE atômico (tentativas < 5 e não vencido):
    pedidos em paralelo não conseguem passar do limite lendo todos "0 tentativas" ao mesmo tempo.
    E o código só é consumido uma vez (DELETE condicionado ao hash)."""
    email = lic.normalizar_email(email)
    codigo = re.sub(r'\D', '', codigo or '')
    agora = datas.agora()
    reservou = db.execute_query(
        "UPDATE apps_codigos_login SET tentativas = tentativas + 1 "
        "WHERE email = %s AND tentativas < %s AND expira_em > %s",
        (email, MAX_TENTATIVAS, agora), return_rowcount=True)
    if not reservou:
        reg = db.execute_query("SELECT expira_em, tentativas FROM apps_codigos_login WHERE email = %s",
                               (email,), fetch_one=True)
        if reg and reg['expira_em'] > agora and reg['tentativas'] >= MAX_TENTATIVAS:
            return None, 'Muitas tentativas. Peça um código novo.'
        return None, 'Esse código venceu. Peça um código novo.'
    consumiu = db.execute_query(
        "DELETE FROM apps_codigos_login WHERE email = %s AND codigo_hash = %s",
        (email, _hash(f'codigo:{email}:{codigo}')), return_rowcount=True)
    if not consumiu:
        return None, 'Código errado. Confira os 6 números no seu email.'
    cliente = lic.buscar_cliente_por_email(email)
    if not cliente:
        return None, 'Não encontramos uma compra com esse email. Use o mesmo email da compra.'
    return cliente['id'], None


# ---------------------------------------------------------------- sessão

def criar_sessao(cliente_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "INSERT INTO apps_sessoes (token_hash, cliente_id, expira_em) VALUES (%s, %s, %s)",
        (_hash(f'sessao:{token}'), cliente_id, datas.agora() + datetime.timedelta(days=SESSAO_DIAS)))
    return token


def cliente_da_sessao(token: str | None):
    if not token:
        return None
    return db.execute_query(
        "SELECT c.id, c.email, c.nome FROM apps_sessoes s JOIN apps_clientes c ON c.id = s.cliente_id "
        "WHERE s.token_hash = %s AND s.expira_em > %s",
        (_hash(f'sessao:{token}'), datas.agora()), fetch_one=True)


def encerrar_sessao(token: str | None) -> None:
    if token:
        db.execute_query("DELETE FROM apps_sessoes WHERE token_hash = %s", (_hash(f'sessao:{token}'),))


def gravar_cookie(resp, token: str):
    resp.set_cookie(COOKIE, token, max_age=SESSAO_DIAS * 86400, path=COOKIE_PATH,
                    httponly=True, samesite='Lax', secure=config.EH_PRODUCAO)
    return resp


def apagar_cookie(resp):
    resp.delete_cookie(COOKIE, path=COOKIE_PATH)
    return resp


# ---------------------------------------------------------------- link de entrada (sem código)

def criar_link_entrada(cliente_id: int, slug: str, minutos: int = LINK_MINUTOS_PADRAO) -> str:
    """Token de uso único para entrar já logada (Estante 2, checkout, link mandado pelo atendimento)."""
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "INSERT INTO apps_links_entrada (token_hash, cliente_id, app_slug, expira_em) VALUES (%s, %s, %s, %s)",
        (_hash(f'link:{token}'), cliente_id, slug, datas.agora() + datetime.timedelta(minutes=minutos)))
    return token


def consumir_link_entrada(token: str, slug: str) -> int | None:
    """Marca o link como usado (uma vez só) e devolve o cliente_id, ou None se inválido/vencido/usado."""
    th = _hash(f'link:{token or ""}')
    with db.get_cursor() as cursor:
        cursor.execute(
            "UPDATE apps_links_entrada SET usado_em = %s "
            "WHERE token_hash = %s AND app_slug = %s AND usado_em IS NULL AND expira_em > %s",
            (datas.agora(), th, slug, datas.agora()))
        if cursor.rowcount == 0:
            return None
        cursor.execute("SELECT cliente_id FROM apps_links_entrada WHERE token_hash = %s", (th,))
        return cursor.fetchone()['cliente_id']


def limpar_vencidos() -> None:
    """Rotina diária: sessões, códigos, links e contadores vencidos."""
    agora = datas.agora()
    with db.get_cursor() as cursor:
        cursor.execute("DELETE FROM apps_sessoes WHERE expira_em < %s", (agora,))
        cursor.execute("DELETE FROM apps_codigos_login WHERE expira_em < %s", (agora,))
        cursor.execute("DELETE FROM apps_links_entrada WHERE expira_em < %s", (agora - datetime.timedelta(days=7),))
        cursor.execute("DELETE FROM apps_pedidos_codigo WHERE criado_em < %s", (agora - datetime.timedelta(days=1),))


# ---------------------------------------------------------------- uso nas rotas

def _host_da_requisicao() -> str:
    return (request.headers.get('X-Forwarded-Host') or request.host or '').split(':')[0].lower()


def origem_confiavel() -> bool:
    """POSTs só do próprio site (proteção contra CSRF: o projeto não tem token CSRF)."""
    origem = request.headers.get('Origin') or request.headers.get('Referer')
    if not origem:
        return False
    return (urlparse(origem).hostname or '').lower() == _host_da_requisicao()


def carregar_cliente(slug: str) -> None:
    """Preenche g.cliente, g.licenca e g.ativa a partir do cookie."""
    g.cliente = cliente_da_sessao(request.cookies.get(COOKIE))
    g.licenca = lic.buscar_licenca(g.cliente['id'], slug) if g.cliente else None
    g.ativa = lic.licenca_ativa(g.licenca)


def pagina(cfg):
    """Tela do app: exige sessão (senão vai para /entrar) e licença deste app (senão, tela 'sem acesso')."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            carregar_cliente(cfg.slug)
            if not g.cliente:
                return redirect(f'{cfg.prefixo}/entrar')
            if not g.licenca:
                from flask import render_template
                return render_template('apps/_nucleo/sem_acesso.html', app=cfg), 403
            try:
                lic.registrar_acesso(g.cliente['id'], cfg.slug)
            except Exception as e:  # o painel de uso nunca pode derrubar a tela
                logger.error(f"[APPS] Erro ao registrar acesso: {e}")
            return f(*args, **kwargs)
        return wrapper
    return deco


def acao(cfg, exige_licenca_ativa: bool = True):
    """POST JSON do app: origem do próprio site, sessão, licença (ativa, se exigido)."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not origem_confiavel():
                return jsonify(ok=False, erro='Pedido recusado. Recarregue a página e tente de novo.'), 403
            carregar_cliente(cfg.slug)
            if not g.cliente:
                return jsonify(ok=False, erro='Sua sessão terminou. Entre de novo.', entrar=True), 401
            if not g.licenca:
                return jsonify(ok=False, erro='Você não tem acesso a este app.'), 403
            if exige_licenca_ativa and not g.ativa:
                return jsonify(ok=False, erro=MSG_LICENCA_VENCIDA), 403
            return f(*args, **kwargs)
        return wrapper
    return deco


def corpo_json() -> dict:
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}
