"""Desconto de oferta (migration 083): o popup "última tentativa" da landing e o cross-sell da
Estante 2 oferecem um produto com desconto.

O desconto fica cadastrado no produto (`produtos.desconto_oferta`); quem mostra a oferta gera um
**token assinado** para o link (`?oferta=<token>`), ligado ao produto e com validade. O checkout
repassa o token e o backend (gerar_pix / gerar_cartao) valida e busca o desconto no banco — nunca
um valor vindo do navegador. Sem token válido, o preço é o cheio (padrão).
"""
import hashlib
import hmac
import logging
import os
import time

from database import db

logger = logging.getLogger(__name__)

VALIDADE_SEGUNDOS = 24 * 3600  # o link da oferta vale 24 h (a cliente pode voltar ao checkout)


def _assinatura(produto_id: int, expira: int) -> str:
    segredo = (os.getenv('SECRET_KEY') or 'troque-em-producao').encode()
    return hmac.new(segredo, f'oferta:{int(produto_id)}:{int(expira)}'.encode(), hashlib.sha256).hexdigest()[:24]


def gerar_token(produto_id: int, agora: float | None = None) -> str:
    expira = int((agora if agora is not None else time.time()) + VALIDADE_SEGUNDOS)
    return f'{expira}.{_assinatura(produto_id, expira)}'


def validar_token(token, produto_id, agora: float | None = None) -> bool:
    """True se o token foi gerado por nós para ESTE produto e ainda vale."""
    try:
        expira_txt, assinatura = str(token or '').split('.', 1)
        expira = int(expira_txt)
        pid = int(produto_id)
    except (TypeError, ValueError):
        return False
    if expira < (agora if agora is not None else time.time()):
        return False
    return hmac.compare_digest(assinatura, _assinatura(pid, expira))


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


def desconto_do_produto(produto_id: int, preco: float, avisar: bool = False) -> float:
    """Desconto de oferta cadastrado no produto, já pela regra única (desconto_valido)."""
    try:
        linha = db.execute_query("SELECT desconto_oferta FROM produtos WHERE id = %s", (produto_id,), fetch_one=True)
    except Exception as e:  # migration 083 ainda não aplicada: sem desconto, checkout segue igual
        logger.error(f"[OFERTA] Erro ao ler o desconto do produto #{produto_id}: {e}")
        return 0.0
    return desconto_valido((linha or {}).get('desconto_oferta'), preco, produto_id, avisar)


def desconto_da_oferta(token, produto_id: int, preco: float) -> float:
    """O desconto a aplicar neste checkout: o do produto, se o token da oferta for válido; senão 0."""
    if not token or not validar_token(token, produto_id):
        return 0.0
    return desconto_do_produto(produto_id, preco, avisar=True)


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
    """Nova tentativa de cartão no MESMO pedido (os itens não são regravados): ajusta o valor do item
    principal ao que será cobrado agora (com ou sem desconto)."""
    try:
        db.execute_query("UPDATE pedido_itens SET valor = %s WHERE pedido_id = %s AND tipo = 'principal'",
                         (round(valor_principal, 2), pedido_id))
    except Exception as e:
        logger.error(f"[OFERTA] Erro ao ajustar o item principal do pedido #{pedido_id}: {e}")


def descontos_dos_produtos(produto_ids) -> dict:
    """{produto_id: desconto_oferta} dos que têm oferta — uma consulta só (cross-sell da Estante)."""
    ids = sorted({int(i) for i in produto_ids if i})
    if not ids:
        return {}
    try:
        linhas = db.execute_query(
            f"SELECT id, desconto_oferta FROM produtos WHERE id IN ({', '.join(['%s'] * len(ids))}) AND desconto_oferta > 0",
            tuple(ids), fetch_all=True) or []
    except Exception as e:
        logger.error(f"[OFERTA] Erro ao ler descontos: {e}")
        return {}
    return {l['id']: float(l['desconto_oferta']) for l in linhas}


def aplicar_na_vitrine(item: dict, descontos: dict) -> dict:
    """Card de cross-sell com oferta: preço com desconto, preço cheio riscado e token no link."""
    preco = float(item['preco_promocional'])
    desconto = desconto_valido(descontos.get(item['produto_id'], 0), preco, item['produto_id'])
    if desconto <= 0:
        return item
    return {**item, 'preco_promocional': round(preco - desconto, 2), 'preco_cheio': preco,
            'oferta': gerar_token(item['produto_id'])}
