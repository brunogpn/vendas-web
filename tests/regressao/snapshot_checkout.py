"""Retrato do comportamento de venda/entrega, para comparar antes e depois de uma refatoração.

Roda DENTRO do container do app, contra o banco de DEV (cria pedidos de teste lá):

    docker compose exec -T -e AMOSTRA_ATE=<último id> app python - < tests/regressao/snapshot_checkout.py > antes.json
    ... refatoração ...
    docker compose exec -T -e AMOSTRA_ATE=<mesmo id> app python - < tests/regressao/snapshot_checkout.py > depois.json
    python3 tests/regressao/comparar_snapshots.py antes.json depois.json

Fotografa, para cada produto à venda no site: HTML do /pay e /pay2 (normalizado), valor e itens do
PIX (sem e com um order bump); para uma amostra de pedidos pagos (web, WhatsApp, antigos): Estante 1
e 2 e o leitor de cada item; o e-mail de entrega; e os itens de um lead do WhatsApp por produto.
Nada é enviado (Gmail desligado) e nada externo é chamado além do que o checkout já faz no dev.
"""
import json
import logging
import os
import re
import sys

logging.disable(logging.CRITICAL)

from app import app  # noqa: E402
import database  # noqa: E402
from database import db  # noqa: E402

EMAIL_TESTE = 'regressao.snapshot@exemplo.com'
# Amostra fixa: só pedidos até este id (os testes criam pedidos pagos novos, que mudariam a amostra).
AMOSTRA_ATE = int(os.environ.get('AMOSTRA_ATE') or 10**12)


def normalizar(html: str) -> str:
    html = re.sub(r'\?v=\d+', '', html)                                         # cache dos estáticos
    html = re.sub(r'data-pedido-id-inicial="\d*"', 'data-pedido-id-inicial="N"', html)
    html = re.sub(r'oferta=[0-9]+\.[0-9a-f]+', 'oferta=TOKEN', html)             # token de oferta
    html = re.sub(r'data-oferta="[^"]*"', 'data-oferta="TOKEN"', html)
    html = re.sub(r'/abrir-app/', '/abrir-app/', html)
    linhas = [l.rstrip() for l in html.splitlines() if l.strip()]
    return '\n'.join(linhas)


def itens_do_pedido(pedido_id):
    return [{'tipo': i['tipo'], 'nome': i['nome'], 'valor': float(i['valor'] or 0),
             'tem_arquivo': bool(i.get('path_arquivo'))}
            for i in database.listar_itens_pedido(pedido_id)]


def pix(cliente, produto_id, bump_ids):
    r = cliente.post('/api/v1/pix/gerar', json={
        'produto_id': produto_id, 'nome': 'Regressao Snapshot', 'email': EMAIL_TESTE,
        'whatsapp': '11988887777', 'bump_ids': bump_ids})
    d = r.get_json(silent=True) or {}
    if not d.get('pedido_id'):
        return {'status': r.status_code, 'resposta': d}
    return {'status': r.status_code, 'valor': d.get('valor'), 'tem_qr': bool(d.get('qrcode_texto')),
            'itens': itens_do_pedido(d['pedido_id'])}


def main():
    c = app.test_client()
    retrato = {'produtos': {}, 'estantes': {}, 'emails': {}, 'whatsapp': {}}

    produtos = db.execute_query(
        "SELECT id FROM produtos WHERE ativo = 1 AND disponivel_web = 1 ORDER BY id", fetch_all=True) or []
    for p in produtos:
        pid = p['id']
        reg = {}
        for rota in ('/pay', '/pay2'):
            r = c.get(f'{rota}/{pid}')
            reg[rota] = {'status': r.status_code, 'html': normalizar(r.get_data(as_text=True))}
        bumps = db.execute_query(
            "SELECT pe.id FROM plano_entregaveis pe JOIN produto_planos pp ON pp.id = pe.plano_id AND pp.padrao = 1 "
            "WHERE pe.produto_id = %s AND pe.papel = 'bump' ORDER BY pe.ordem, pe.id LIMIT 1",
            (pid,), fetch_one=True)
        reg['pix_sem_bump'] = pix(c, pid, [])
        reg['pix_com_bump'] = pix(c, pid, [bumps['id']]) if bumps else None
        retrato['produtos'][str(pid)] = reg

    # Amostra de pedidos pagos: web recentes, WhatsApp recentes e antigos (itens sem vínculo ao catálogo).
    amostra = db.execute_query("""
        (SELECT id, guid FROM pedidos WHERE estado_id = 1000 AND guid IS NOT NULL AND email <> %s AND id <= %s
          ORDER BY id DESC LIMIT 8)
        UNION
        (SELECT id, guid FROM pedidos WHERE estado_id = 0 AND guid IS NOT NULL AND id <= %s ORDER BY id DESC LIMIT 6)
        UNION
        (SELECT p.id, p.guid FROM pedidos p JOIN pedido_itens pi ON pi.pedido_id = p.id
          WHERE p.guid IS NOT NULL AND pi.ebook_produto_id IS NULL AND pi.path_arquivo IS NOT NULL
            AND p.id <= %s AND p.email <> %s
          GROUP BY p.id ORDER BY p.id LIMIT 4)
    """, (EMAIL_TESTE, AMOSTRA_ATE, AMOSTRA_ATE, AMOSTRA_ATE, EMAIL_TESTE), fetch_all=True) or []
    for p in sorted(amostra, key=lambda x: x['id']):
        g = p['guid']
        reg = {}
        for rota in (f'/pedido/{g}', f'/pedido2/{g}'):
            r = c.get(rota)
            reg[rota.split('/')[1]] = {'status': r.status_code, 'html': normalizar(r.get_data(as_text=True))}
        leitor = {}
        for item in database.listar_itens_pedido(p['id']):
            leitor[f"{item['tipo']}:{item['nome']}"] = c.get(f"/pedido/{g}/ler/{item['id']}").status_code
        reg['leitor'] = leitor
        retrato['estantes'][str(p['id'])] = reg

    # E-mail de entrega (sem enviar): os mesmos pedidos web da amostra.
    import fluxos.entrega_pedido_email as ent
    enviados = []
    original = {k: getattr(database, k) for k in ('get_pedido', 'marcar_ebook_enviado',
                                                    'definir_gmail_thread_pedido', 'salvar_mensagem_email_pedido')}
    original_ent = {'_enviar_gmail': ent._enviar_gmail, 'rotular_enviado': ent.rotular_enviado}
    ent._enviar_gmail = lambda **k: enviados.append(k) or {'id': 'snapshot'}
    ent.rotular_enviado = lambda *a: None
    database.marcar_ebook_enviado = lambda i: None
    database.definir_gmail_thread_pedido = lambda *a: None
    database.salvar_mensagem_email_pedido = lambda **k: None
    database.get_pedido = lambda i: {**original['get_pedido'](i), 'data_envio_ebook': None}
    try:
        for p in sorted(amostra, key=lambda x: x['id']):
            ped = original['get_pedido'](p['id'])
            if ped['estado_id'] != 1000 or not ped.get('email'):
                continue
            enviados.clear()
            ent.executar(p['id'])
            if enviados:
                retrato['emails'][str(p['id'])] = {'assunto': enviados[0]['subject'],
                                                  'html': normalizar(enviados[0]['html'])}
    finally:
        for k, v in original.items():
            setattr(database, k, v)
        for k, v in original_ent.items():
            setattr(ent, k, v)

    # Lead do WhatsApp: itens gravados na criação do pedido, por produto.
    for p in db.execute_query("SELECT id FROM produtos WHERE ativo = 1 ORDER BY id", fetch_all=True) or []:
        pid = database.criar_pedido({'produto_id': p['id'], 'contact_phone': '5511900000099',
                                     'contact_name': 'Lead Snapshot', 'phone_number_id': 'snapshot',
                                     'valor_pago': 10.0})
        retrato['whatsapp'][str(p['id'])] = itens_do_pedido(pid)

    json.dump(retrato, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)


main()
