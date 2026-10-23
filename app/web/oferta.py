"""Desconto de oferta: o popup "última tentativa" da landing e o cross-sell da Estante 2 oferecem um
plano com desconto.

O desconto fica cadastrado no plano (`produto_planos.desconto_oferta`, migration 085); quem mostra a
oferta gera um **token assinado** para o link (`?oferta=<token>`), ligado ao produto, ao plano e com
validade. O checkout repassa o token e o backend (gerar_pix / gerar_cartao) valida e busca o desconto
no banco — nunca um valor vindo do navegador. Sem token válido, o preço é o cheio (padrão).
"""
import hashlib
import hmac
import logging
import os
import time

from database import db

logger = logging.getLogger(__name__)

VALIDADE_SEGUNDOS = 24 * 3600  # o link da oferta vale 24 h (a cliente pode voltar ao checkout)


def _assinatura(produto_id: int, plano_id: int, expira: int) -> str:
    segredo = (os.getenv('SECRET_KEY') or 'troque-em-producao').encode()
    msg = f'oferta:{int(produto_id)}:{int(plano_id)}:{int(expira)}'.encode()
    return hmac.new(segredo, msg, hashlib.sha256).hexdigest()[:24]


def gerar_token(produto_id: int, plano_id: int, agora: float | None = None) -> str:
    expira = int((agora if agora is not None else time.time()) + VALIDADE_SEGUNDOS)
    return f'{expira}.{_assinatura(produto_id, plano_id, expira)}'


def _assinatura_sem_plano(produto_id: int, expira: int) -> str:
    """Formato de antes da migration 085 (só produto). Links emitidos antes do deploy valem 24 h."""
    segredo = (os.getenv('SECRET_KEY') or 'troque-em-producao').encode()
    return hmac.new(segredo, f'oferta:{int(produto_id)}:{int(expira)}'.encode(), hashlib.sha256).hexdigest()[:24]


def validar_token(token, produto_id, plano_id, agora: float | None = None, plano_padrao: bool = False) -> bool:
    """True se o token foi gerado por nós para ESTE produto e plano e ainda vale. Token do formato antigo
    (sem plano, emitido antes da migration 085) vale para o plano padrão — era o único que existia."""
    try:
        expira_txt, assinatura = str(token or '').split('.', 1)
        expira = int(expira_txt)
        pid, plid = int(produto_id), int(plano_id)
    except (TypeError, ValueError):
        return False
    if expira < (agora if agora is not None else time.time()):
        return False
    if hmac.compare_digest(assinatura, _assinatura(pid, plid, expira)):
        return True
    # TODO(depois de 19/10/2026): remover — todo token sem plano já venceu (validade de 24 h).
    return plano_padrao and hmac.compare_digest(assinatura, _assinatura_sem_plano(pid, expira))


def desconto_valido(desconto, preco, produto_id=None, avisar: bool = False) -> float:
    """REGRA ÚNICA do desconto (checkout, landing, Estante): vale se for > 0 e MENOR que o preço.
    Desconto maior ou igual ao preço (ex.: o preço foi baixado depois de cadastrar a oferta) é
    ignorado — preço cheio — em vez de vender por centavos. O admin também recusa salvar assim."""
    desconto, preco = float(desconto or 0), float(preco or 0)
    if desconto <= 0:
        return 0.0
    if desconto >= preco:
        if avisar:  # só no checkout (vitrine/landing chamam a cada visita: não encher o log)
            logger.warning(f"[OFERTA] Desconto R$ {desconto:.2f} >= preço R$ {preco:.2f} no produto #{produto_id} — ignorado")
        return 0.0
    return round(desconto, 2)


def desconto_do_plano(plano: dict, preco: float, avisar: bool = False) -> float:
    """Desconto de oferta cadastrado no plano, já pela regra única (desconto_valido)."""
    return desconto_valido(plano.get('desconto_oferta'), preco, plano.get('produto_id'), avisar)


def oferta_do_plano(plano: dict, preco: float, **link) -> dict | None:
    """A oferta pronta para mostrar (popup "última chance" das landings e da prévia da Música): preço cheio,
    preço com desconto, economia e o link do checkout com o token. `link` = parâmetros extras de
    link_checkout (ex.: musica=<token>). None = o plano não tem desconto válido."""
    from web.links import link_checkout
    desconto = desconto_do_plano(plano, preco)
    if desconto <= 0:
        return None
    token = gerar_token(plano['produto_id'], plano['id'])
    return {'preco_cheio': preco, 'preco_promocional': round(preco - desconto, 2), 'economia': desconto,
            'href': link_checkout(plano['produto_id'], plano, oferta=token, **link),
            'expira': int(token.split('.', 1)[0])}   # quando o link deixa de dar o desconto (epoch, segundos)


def desconto_da_oferta(token, plano: dict, preco: float) -> float:
    """O desconto a aplicar neste checkout: o do plano, se o token da oferta for válido para ele; senão 0."""
    if not token or not validar_token(token, plano['produto_id'], plano['id'], plano_padrao=bool(plano.get('padrao'))):
        return 0.0
    return desconto_do_plano(plano, preco, avisar=True)


def oferta_divergente(body: dict, desconto: float) -> dict | None:
    """O checkout mostrou um desconto (data-desconto) diferente do que o backend aplicaria agora
    (token venceu com a página aberta, admin mudou a oferta...): não cobra diferente do que a cliente
    viu — devolve o aviso para o front recarregar a página com o preço certo."""
    try:
        exibido = float(body.get('desconto_exibido') or 0)
    except (TypeError, ValueError):
        exibido = 0.0
    if abs(exibido - desconto) > 0.009:
        return {'oferta_alterada': True,
                'mensagem': 'O valor da oferta mudou desde que você abriu esta página. Vamos atualizar o preço.'}
    return None


def gravar_desconto_pedido(pedido_id: int, desconto: float, sempre: bool = False) -> None:
    """Grava o desconto aplicado no pedido. Sem desconto não escreve nada: o pedido reaproveitado é
    sempre um rascunho (1003/1004, nunca teve desconto) e um PIX refeito cria pedido novo (default 0).
    `sempre=True` (retry de cartão negado, mesmo pedido): grava mesmo 0, para o pedido nunca ficar com
    um desconto que não foi cobrado."""
    if desconto <= 0 and not sempre:
        return
    try:
        db.execute_query("UPDATE pedidos SET desconto = %s WHERE id = %s", (round(desconto, 2), pedido_id))
    except Exception as e:
        logger.error(f"[OFERTA] Erro ao gravar o desconto do pedido #{pedido_id}: {e}")


def sincronizar_item_principal(pedido_id: int, valor_principal: float) -> None:
    """Nova tentativa de cartão no MESMO pedido (os itens não são regravados): ajusta o valor do
    primeiro item principal (o que leva o preço do plano) ao que será cobrado agora (com ou sem desconto)."""
    try:
        db.execute_query("UPDATE pedido_itens SET valor = %s WHERE pedido_id = %s AND tipo = 'principal' "
                         "ORDER BY id LIMIT 1", (round(valor_principal, 2), pedido_id))
    except Exception as e:
        logger.error(f"[OFERTA] Erro ao ajustar o item principal do pedido #{pedido_id}: {e}")


def aplicar_na_vitrine(item: dict) -> dict:
    """Card de cross-sell (um plano: produto_id, plano_id, preco_promocional, desconto_oferta) com
    oferta: preço com desconto, preço cheio riscado e token no link."""
    preco = float(item['preco_promocional'])
    desconto = desconto_valido(item.get('desconto_oferta'), preco, item['produto_id'])
    if desconto <= 0:
        return item
    return {**item, 'preco_promocional': round(preco - desconto, 2), 'preco_cheio': preco,
            'oferta': gerar_token(item['produto_id'], item['plano_id'])}
