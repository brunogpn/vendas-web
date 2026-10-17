"""Telas e ações do App Fatias (/app/fatia/). Especificação em docs/APP_FATIA_ESPECIFICACAO.md.

Telas: GET, montadas no servidor (Jinja). Ações: POST JSON via App.post (static/apps/_nucleo/app.js),
sempre com {ok, erro?} e, quando muda o progresso, {conquistas} para a comemoração.
Com a licença vencida a cliente vê tudo, mas só consegue editar o perfil.
"""
from functools import lru_cache, wraps

from flask import Blueprint, g, jsonify, redirect, render_template, request

from apps._nucleo import auth, datas, estante, formato, licenca as lic
from apps.fatia import dados, progresso as prog, receitas as rec
from apps.fatia.config import CONFIG
from apps.fatia.conteudo import (FASE_POR_NUMERO, FASES, GRUPOS_INGREDIENTES, INGREDIENTE_POR_ID,
                                 INGREDIENTES, PASSO_POR_ID, PASSOS, POSICAO, TOTAL_PASSOS)

bp = Blueprint('app_fatia', __name__, url_prefix=CONFIG.prefixo, template_folder='../templates')

P = CONFIG.prefixo


# ---------------------------------------------------------------- base das telas

def tela(menu: str | None = None, onboarding: bool = False):
    """Tela do app: sessão + licença (núcleo), perfil carregado e boas-vindas obrigatória no 1º acesso."""
    def deco(f):
        @auth.pagina(CONFIG)
        @wraps(f)
        def wrapper(*args, **kwargs):
            g.perfil = dados.perfil(g.cliente['id'])
            g.menu = menu
            fez = bool(g.perfil['onboarding_ok'])
            if not onboarding and not fez:
                return redirect(f'{P}/boas-vindas')
            if onboarding and fez:
                return redirect(f'{P}/')
            return f(*args, **kwargs)
        return wrapper
    return deco


def _render(template: str, **ctx):
    dias = lic.dias_restantes(g.licenca)
    return render_template(
        f'apps/fatia/{template}', app=CONFIG, cliente=g.cliente, perfil=g.perfil, ativa=g.ativa,
        licenca=g.licenca, dias_licenca=dias, menu=g.menu, som_ligado=bool(g.perfil.get('som')),
        fmt=formato, datas=datas, P=P, primeiro_nome=_primeiro_nome(), **ctx)


def _primeiro_nome() -> str:
    nome = (g.perfil.get('nome') or (g.cliente or {}).get('nome') or '').strip()
    return nome.split(' ')[0] if nome else ''


def _link_interno(href: str) -> str:
    """Links do conteúdo (trilha) são relativos ao app: '/receitas' → '/app/fatia/receitas'."""
    return f'{P}{href}' if href.startswith('/') else href


# ---------------------------------------------------------------- boas-vindas e perfil

@bp.get('/boas-vindas')
@tela(onboarding=True)
def boas_vindas():
    nome = _primeiro_nome()
    return _render('boas_vindas.html', nome_inicial=nome, dias_semana=prog.DIAS_SEMANA,
                   metas_opcoes=[1000, 2000, 3000, 5000, 8000, 10000])


# Teto dos números digitados: bem acima de qualquer valor real, e abaixo do que cabe nas colunas
# DECIMAL(10,2)/INT. Sem isso, um dígito a mais virava erro do banco (tela "Algo deu errado").
MAX_DINHEIRO = 1_000_000
MAX_FATIAS = 100_000
MAX_EMBALAGEM = 1_000_000
MSG_GRANDE_DEMAIS = 'Esse valor parece grande demais. Confira os números.'


def _limpar_perfil(corpo: dict) -> dict:
    campos = {}
    if 'nome' in corpo:
        campos['nome'] = (str(corpo.get('nome') or '').strip()[:60]) or None
    for k in ('meta_mensal', 'investimento', 'preco_fatia', 'custo_fatia'):
        if k in corpo:
            v = corpo.get(k)
            campos[k] = None if v is None else round(max(0.0, formato.ler_numero(v)), 2)
    if 'dias_venda' in corpo:
        validos = [d for d, _ in prog.DIAS_SEMANA]
        escolhidos = corpo.get('dias_venda') or []
        if isinstance(escolhidos, str):
            escolhidos = escolhidos.split(',')
        campos['dias_venda'] = ','.join(d for d in validos if d in escolhidos) or None
    for k in ('som', 'onboarding_ok'):
        if k in corpo:
            campos[k] = 1 if corpo.get(k) else 0
    return campos


@bp.post('/perfil')
@auth.acao(CONFIG, exige_licenca_ativa=False)  # o perfil continua editável com a licença vencida
def salvar_perfil():
    campos = _limpar_perfil(auth.corpo_json())
    if any((campos.get(k) or 0) > MAX_DINHEIRO for k in ('meta_mensal', 'investimento', 'preco_fatia', 'custo_fatia')):
        return jsonify(ok=False, erro=MSG_GRANDE_DEMAIS), 400
    if 'meta_mensal' in campos and not campos['meta_mensal']:
        return jsonify(ok=False, erro='Escolha quanto você quer ganhar por mês.'), 400
    dados.salvar_perfil(g.cliente['id'], campos)
    perfil = dados.perfil(g.cliente['id'])
    m = prog.metas(perfil)
    return jsonify(ok=True, fatias_por_semana=m['fatias_por_semana'], meta=m['meta'])


@bp.get('/perfil')
@tela(menu='mais')
def perfil():
    return _render('perfil.html', dias_semana=prog.DIAS_SEMANA)


# ---------------------------------------------------------------- início

@bp.get('/')
@tela(menu='inicio')
def inicio():
    p = prog.progresso(g.cliente['id'], g.perfil)
    faceis = [r for r in rec.RECEITAS if r['categoria'] == 'fatias' and r.get('dificuldade') == 'fácil' and r.get('imagem')][:6]
    return _render('inicio.html', p=p, hoje=datas.hoje(), faceis=faceis, total_passos=TOTAL_PASSOS,
                   nome_mes=datas.nome_mes(datas.mes_atual()))


# ---------------------------------------------------------------- trilha

@bp.get('/tarefas')
@tela(menu='tarefas')
def tarefas():
    p = prog.progresso(g.cliente['id'], g.perfil)
    fases = []
    for f in FASES:
        passos = [x for x in PASSOS if x['fase'] == f['numero']]
        fases.append({**f, 'passos': passos, 'feitos': sum(1 for x in passos if x['id'] in p['feitas'])})
    atual = p['proximo_passo']['id'] if p['proximo_passo'] else None
    return _render('tarefas.html', p=p, fases=fases, atual=atual, total_passos=TOTAL_PASSOS)


def _liberado(feitas: set, tarefa_id: int) -> bool:
    i = POSICAO[tarefa_id]
    return i == 0 or PASSOS[i - 1]['id'] in feitas


def _ultimo_feito(feitas: set):
    """Último passo concluído na ordem da trilha (o único que dá para desmarcar)."""
    for passo in reversed(PASSOS):
        if passo['id'] in feitas:
            return passo['id']
    return None


@bp.get('/tarefas/<int:tarefa_id>')
@tela(menu='tarefas')
def tarefa(tarefa_id):
    passo = PASSO_POR_ID.get(tarefa_id)
    if not passo:
        return redirect(f'{P}/tarefas')
    p = prog.progresso(g.cliente['id'], g.perfil)
    i = POSICAO[tarefa_id]
    proximo = PASSOS[i + 1]['id'] if i + 1 < len(PASSOS) else None
    link = dict(passo['link'], href=_link_interno(passo['link']['href'])) if passo.get('link') else None
    return _render('tarefa.html', passo=passo, numero=i + 1, fase=FASE_POR_NUMERO[passo['fase']],
                   feito=tarefa_id in p['feitas'], concluida_em=p['concluidas_em'].get(tarefa_id),
                   liberado=_liberado(p['feitas'], tarefa_id), pode_desfazer=_ultimo_feito(p['feitas']) == tarefa_id,
                   proximo=proximo, link=link, ultimo=proximo is None)


@bp.post('/tarefas/<int:tarefa_id>/concluir')
@auth.acao(CONFIG)
def concluir_tarefa(tarefa_id):
    if tarefa_id not in PASSO_POR_ID:
        return jsonify(ok=False, erro='Tarefa não encontrada.'), 404
    cid = g.cliente['id']
    perfil = dados.perfil(cid)
    antes = prog.progresso(cid, perfil)
    if not _liberado(antes['feitas'], tarefa_id):
        return jsonify(ok=False, erro='Conclua o passo anterior primeiro.'), 400
    dados.concluir_tarefa(cid, tarefa_id)
    depois = prog.progresso(cid, perfil)
    return jsonify(ok=True, conquistas=prog.conquistas(antes, depois))


@bp.post('/tarefas/<int:tarefa_id>/desfazer')
@auth.acao(CONFIG)
def desfazer_tarefa(tarefa_id):
    feitas = {t['tarefa_id'] for t in dados.tarefas_concluidas(g.cliente['id'])}
    if _ultimo_feito(feitas) != tarefa_id:
        return jsonify(ok=False, erro='Só dá para desmarcar o último passo concluído.'), 400
    dados.desfazer_tarefa(g.cliente['id'], tarefa_id)
    return jsonify(ok=True)


# ---------------------------------------------------------------- receitas

@bp.get('/receitas')
@tela(menu='receitas')
def receitas():
    lista = [{**rec.resumo(r), 'busca': rec.sem_acento(r['nome'])} for r in rec.RECEITAS_DE_VENDA]
    categoria = request.args.get('categoria') if request.args.get('categoria') in rec.CATEGORIAS_DE_VENDA else 'fatias'
    contagem = {c: sum(1 for r in rec.RECEITAS_DE_VENDA if r['categoria'] == c) for c in rec.CATEGORIAS_DE_VENDA}
    return _render('receitas.html', receitas=lista, categoria=categoria, busca=request.args.get('busca', ''),
                   contagem=contagem, categorias=rec.CATEGORIA_POR_ID)


def _partes_versao(r: dict, texto: str) -> list[dict]:
    """'Massa Black + Ganache meio amarga' → partes, cada uma com a receita-base citada (se houver).
    Não vira link se o nome da parte é um grupo de ingredientes da própria receita."""
    grupos = {rec.sem_acento(gr['titulo']) for gr in r['ingredientes']}
    partes = []
    for parte in [s.strip() for s in texto.split(' + ')]:
        base = None if rec.sem_acento(parte) in grupos else rec.base_citada(parte)
        partes.append({'texto': parte, 'base': base})
    return partes


@bp.get('/receitas/<rid>')
@tela(menu='receitas')
def receita(rid):
    r = rec.receita(rid)
    if not r:
        return redirect(f'{P}/receitas')
    de_venda = r['categoria'] in rec.CATEGORIAS_DE_VENDA
    versoes = [{'nome': c['nome'], 'partes': _partes_versao(r, c['texto'])} for c in r['combinacoes']]
    usa = [rec.receita(u) for u in r['usa'] if rec.receita(u)]
    return _render('receita.html', r=r, de_venda=de_venda, categoria=rec.CATEGORIA_POR_ID[r['categoria']],
                   versoes=versoes, usa=usa, usada_por=rec.usadas_por(rid), por_id=rec.POR_ID,
                   ebook=rec.EBOOK_DA_CATEGORIA.get(r['categoria'], 'Bolos Caseiros'),
                   varios_grupos_ing=len(r['ingredientes']) > 1, varios_grupos_prep=len(r['preparo']) > 1)


# ---------------------------------------------------------------- vendas

@bp.get('/vendas')
@tela(menu='vendas')
def vendas():
    p = prog.progresso(g.cliente['id'], g.perfil)
    hoje = datas.hoje()
    vendas_json = [{'data': datas.como_data(l['data']).isoformat(), 'gasto': l['gasto'], 'fatias': l['fatias'],
                    'recebido': l['recebido']} for l in p['vendas']]
    return _render('vendas.html', p=p, hoje=hoje, nome_mes=datas.nome_mes(datas.mes_atual()), vendas_json=vendas_json)


@bp.post('/vendas/salvar')
@auth.acao(CONFIG)
def salvar_venda():
    corpo = auth.corpo_json()
    try:
        data = datas.como_data(corpo.get('data'))
    except ValueError:
        data = None
    if not data or data > datas.hoje():
        return jsonify(ok=False, erro='Escolha uma data de hoje ou de antes.'), 400
    gasto = round(max(0.0, formato.ler_numero(corpo.get('gasto'))), 2)
    fatias = int(round(max(0.0, formato.ler_numero(corpo.get('fatias')))))
    recebido = round(max(0.0, formato.ler_numero(corpo.get('recebido'))), 2)
    if gasto > MAX_DINHEIRO or recebido > MAX_DINHEIRO or fatias > MAX_FATIAS:
        return jsonify(ok=False, erro=MSG_GRANDE_DEMAIS), 400
    cid = g.cliente['id']
    perfil = dados.perfil(cid)
    antes = prog.progresso(cid, perfil)
    dados.salvar_lancamento(cid, data, gasto, fatias, recebido)
    depois = prog.progresso(cid, perfil)
    return jsonify(ok=True, conquistas=prog.conquistas(antes, depois))


@bp.post('/vendas/apagar')
@auth.acao(CONFIG)
def apagar_venda():
    try:
        data = datas.como_data(auth.corpo_json().get('data'))
    except ValueError:
        data = None
    if not data:
        return jsonify(ok=False, erro='Dia inválido.'), 400
    dados.apagar_lancamento(g.cliente['id'], data)
    return jsonify(ok=True)


# ---------------------------------------------------------------- mais, medalhas, acesso, e-books

@bp.get('/mais')
@tela(menu='mais')
def mais():
    return _render('mais.html')


@bp.get('/medalhas')
@tela(menu='mais')
def medalhas():
    p = prog.progresso(g.cliente['id'], g.perfil)
    return _render('medalhas.html', p=p, niveis=prog.NIVEIS, pontos_tarefa=prog.PONTOS_TAREFA,
                   pontos_dia=prog.PONTOS_DIA_LANCADO)


@bp.get('/acesso')
@tela(menu='mais')
def acesso():
    from database import listar_planos_com_app
    from web.links import link_checkout
    from apps._nucleo import licenca as lic
    # Renovações = planos de renovação deste app (admin, "Planos e entregáveis") SÓ do produto em que ela
    # comprou o app (ex.: Completo do 12 → renovação do 12). Sem compra (licença manual) ou sem renovação
    # cadastrada nesse produto: a tela mostra o contato do suporte.
    ref = estante.pedido_da_estante(g.cliente, CONFIG.slug)
    produto_id = lic.produto_de_origem(g.cliente['id'], CONFIG.slug)
    planos = (listar_planos_com_app(CONFIG.slug, renovacao=True, so_venda_web=True, produto_id=produto_id)
              if produto_id else [])
    renovacoes = [{**r, 'meses': max(1, round(r['dias'] / 30)),
                   'href': link_checkout(r['produto_id'], r, v2=bool(ref), ref=ref['guid'] if ref else None)}
                  for r in planos]
    return _render('acesso.html', expira_em=g.licenca['expira_em'], renovacoes=renovacoes,
                   guid_estante=ref['guid'] if ref else None)


@bp.get('/ebooks')
@tela(menu='mais')
def ebooks():
    guid, itens = estante.ebooks_da_cliente(g.cliente, CONFIG.slug)
    return _render('ebooks.html', guid=guid, itens=itens)


# ---------------------------------------------------------------- preços, calculadora, lista

# O conteúdo (receitas, ingredientes) é carregado uma vez na importação e não muda com o app no
# ar: estas listas são montadas uma vez só (só leitura — vão direto para o tojson das telas).
@lru_cache(maxsize=1)
def _catalogo_json() -> list[dict]:
    return [{'id': i['id'], 'nome': i['nome'], 'unidade': i['unidade'], 'embalagem': i['embalagem'],
             'rotuloEmbalagem': i['rotuloEmbalagem'], 'grupo': i['grupo'], 'busca': rec.sem_acento(i['nome'])}
            for i in INGREDIENTES]


@lru_cache(maxsize=1)
def _receitas_custo_json() -> list[dict]:
    return [{**rec.receita_custo(r), 'busca': rec.sem_acento(r['nome'])} for r in rec.RECEITAS_DE_VENDA]


@bp.get('/precos')
@tela(menu='mais')
def precos():
    return _render('precos.html', catalogo=_catalogo_json(), grupos=GRUPOS_INGREDIENTES,
                   precos=dados.mapa_precos(g.cliente['id']))


@bp.post('/precos/salvar')
@auth.acao(CONFIG)
def salvar_preco():
    corpo = auth.corpo_json()
    item = str(corpo.get('item') or '')
    if item not in INGREDIENTE_POR_ID:
        return jsonify(ok=False, erro='Ingrediente não encontrado.'), 400
    preco = round(formato.ler_numero(corpo.get('preco')), 2)
    quantidade = round(formato.ler_numero(corpo.get('quantidade')), 2)
    if preco <= 0 or quantidade <= 0:
        return jsonify(ok=False, erro='Preencha o preço e o tamanho da embalagem.'), 400
    if preco > MAX_DINHEIRO or quantidade > MAX_EMBALAGEM:
        return jsonify(ok=False, erro=MSG_GRANDE_DEMAIS), 400
    dados.salvar_preco(g.cliente['id'], item, preco, quantidade)
    return jsonify(ok=True, preco={'preco': preco, 'quantidade': quantidade})


@bp.post('/precos/apagar')
@auth.acao(CONFIG)
def apagar_preco():
    item = str(auth.corpo_json().get('item') or '')
    if item not in INGREDIENTE_POR_ID:
        return jsonify(ok=False, erro='Ingrediente não encontrado.'), 400
    dados.apagar_preco(g.cliente['id'], item)
    return jsonify(ok=True)


@bp.get('/calculadora')
@tela(menu='mais')
def calculadora():
    rid = request.args.get('receita')
    escolhida = rid if rid and rec.receita(rid) and rec.receita(rid)['categoria'] in rec.CATEGORIAS_DE_VENDA else None
    lista = dados.lista_compras(g.cliente['id'])
    return _render('calculadora.html', catalogo=_catalogo_json(), receitas=_receitas_custo_json(),
                   precos=dados.mapa_precos(g.cliente['id']), escolhida=escolhida,
                   na_lista=list(lista['receitas'].keys()), metas=prog.metas(g.perfil))


@bp.get('/lista')
@tela(menu='mais')
def lista():
    cid = g.cliente['id']
    lista = dados.lista_compras(cid)
    # Receitas que saíram do conteúdo somem da lista.
    lista['receitas'] = {k: v for k, v in lista['receitas'].items() if k in rec.POR_ID}
    adicionar = request.args.get('adicionar')
    if adicionar and adicionar in rec.POR_ID and rec.POR_ID[adicionar]['categoria'] in rec.CATEGORIAS_DE_VENDA:
        if adicionar not in lista['receitas'] and g.ativa:
            lista['receitas'][adicionar] = 1
            dados.salvar_lista_compras(cid, lista)
        return redirect(f'{P}/lista')
    return _render('lista.html', catalogo=_catalogo_json(), receitas=_receitas_custo_json(),
                   precos=dados.mapa_precos(cid), lista=lista)


@bp.post('/lista/salvar')
@auth.acao(CONFIG)
def salvar_lista():
    corpo = auth.corpo_json()
    receitas_in = corpo.get('receitas') if isinstance(corpo.get('receitas'), dict) else {}
    marcados_in = corpo.get('marcados') if isinstance(corpo.get('marcados'), list) else []
    receitas_ok = {}
    for rid, vezes in list(receitas_in.items())[:100]:
        try:
            vezes = int(vezes)
        except (TypeError, ValueError):
            continue
        if isinstance(rid, str) and len(rid) <= 100 and rid in rec.POR_ID and 1 <= vezes <= 50:
            receitas_ok[rid] = vezes
    marcados_ok = [m for m in marcados_in[:500] if isinstance(m, str) and len(m) <= 300]
    dados.salvar_lista_compras(g.cliente['id'], {'receitas': receitas_ok, 'marcados': marcados_ok})
    return jsonify(ok=True)
