"""Receitas do App Fatias, lidas dos .txt em conteudo/receitas/ (formato em LEIAME.md).

É o porte do scripts/gerar-receitas.mjs + src/lib/receitas.ts do projeto do Bruno: as receitas são
lidas uma vez (na importação) e, se algo estiver errado no texto, o import falha com a lista de
erros — melhor quebrar no deploy do que mostrar receita pela metade.
"""
import os
import re
import unicodedata

from apps.fatia.conteudo import INGREDIENTE_POR_ID

_PASTA = os.path.join(os.path.dirname(__file__), 'conteudo', 'receitas')
_FOTOS = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'static', 'apps', 'fatia', 'receitas')

CATEGORIAS = [
    {'id': 'fatias', 'nome': 'Fatias', 'icone': 'Cake'},
    {'id': 'brigadeiros', 'nome': 'Brigadeiros', 'icone': 'Cookie'},
    {'id': 'massas', 'nome': 'Massas', 'icone': 'CookingPot'},
    {'id': 'recheios', 'nome': 'Recheios', 'icone': 'Jar'},
    {'id': 'caldas', 'nome': 'Caldas', 'icone': 'Drop'},
    {'id': 'coberturas', 'nome': 'Coberturas', 'icone': 'Sparkle'},
    {'id': 'geleias', 'nome': 'Geleias', 'icone': 'Plant'},
]
CATEGORIA_POR_ID = {c['id']: c for c in CATEGORIAS}
# Receitas que rendem fatias/unidades para vender: aparecem na lista e entram na calculadora.
CATEGORIAS_DE_VENDA = ('fatias', 'brigadeiros')

EBOOK_DA_CATEGORIA = {'fatias': 'Fatias de Bolo', 'brigadeiros': 'Brigadeiros sem Fogo'}  # o resto: Bolos Caseiros

_CAMPOS = {'desc': 'descricao', 'rend': 'rendimento', 'val': 'validade', 'dif': 'dificuldade',
           'dica': 'dica', 'combina': 'combina', 'un': 'unidade'}
_RE_CAMPO = re.compile(r'^(desc|rend|fatias|val|selos|dif|usa|dica|combina|un|obs):\s*(.*)$')
_RE_TAG = re.compile(r'\s*\[(~?)([a-z-]+)\s+([\d.]+)\]\s*$')
_RE_LINK = re.compile(r'\{([a-z0-9-]+)\}')


class ErroReceitas(Exception):
    pass


def _numero(texto):
    n = float(texto)
    return int(n) if n.is_integer() else n


def ler_receitas(pasta: str = _PASTA, fotos: str = _FOTOS) -> list[dict]:
    receitas, erros = [], []
    atual, modo = None, None
    for arquivo in sorted(f for f in os.listdir(pasta) if f.endswith('.txt')):
        with open(os.path.join(pasta, arquivo), encoding='utf-8') as f:
            linhas = f.read().split('\n')
        for i, bruta in enumerate(linhas):
            linha = bruta.strip()
            onde = f'{arquivo}:{i + 1}'
            if not linha or (linha.startswith('#') and not linha.startswith('##')):
                continue
            if linha.startswith('@ '):
                partes = [s.strip() for s in linha[2:].split('|')]
                partes += [''] * (4 - len(partes))
                atual = {'id': partes[0], 'nome': partes[1], 'categoria': partes[2],
                         'pagina': int(partes[3]) if partes[3] else None,
                         'ingredientes': [], 'preparo': [], 'combinacoes': [], 'usa': [], 'observacoes': [],
                         'selos': []}
                receitas.append(atual)
                modo = None
                continue
            if atual is None:
                erros.append(f'{onde}: linha fora de receita')
                continue
            campo = _RE_CAMPO.match(linha)
            if campo:
                chave, valor = campo.groups()
                if chave == 'obs':
                    atual['observacoes'].append(valor)
                elif chave == 'fatias':
                    atual['fatias'] = _numero(valor)
                elif chave == 'selos':
                    atual['selos'] = [s.strip() for s in valor.split(';')]
                elif chave == 'usa':
                    atual['usa'] = [s.strip() for s in valor.split(',')]
                else:
                    atual[_CAMPOS[chave]] = valor
                continue
            if linha.startswith('### '):
                modo = 'preparo'
                atual['preparo'].append({'titulo': linha[4:], 'itens': []})
                continue
            if linha.startswith('## '):
                modo = 'ingredientes'
                atual['ingredientes'].append({'titulo': linha[3:], 'itens': []})
                continue
            if linha.startswith('> '):
                nome, _, resto = linha[2:].partition(':')
                atual['combinacoes'].append({'nome': nome.strip(), 'texto': resto.strip()})
                continue
            if linha.startswith('- ') and modo == 'ingredientes':
                texto = linha[2:]
                item = {}
                tag = _RE_TAG.search(texto)
                if tag:
                    texto = texto[:tag.start()]
                    item['item'] = tag.group(2)
                    item['qtd'] = _numero(tag.group(3))
                    if tag.group(1):
                        item['estimado'] = True
                links = _RE_LINK.findall(texto)
                if links:
                    item['links'] = links
                    texto = re.sub(r'\s*\{[a-z0-9-]+\}', '', texto)
                item['texto'] = texto
                atual['ingredientes'][-1]['itens'].append(item)
                continue
            if linha.startswith('* ') and modo == 'preparo':
                atual['preparo'][-1]['itens'].append(linha[2:])
                continue
            erros.append(f'{onde}: não entendi "{linha}"')

    ids = set()
    for r in receitas:
        if r['id'] in ids:
            erros.append(f'id repetido: {r["id"]}')
        ids.add(r['id'])
        if r['categoria'] not in CATEGORIA_POR_ID:
            erros.append(f'{r["id"]}: categoria desconhecida "{r["categoria"]}"')
        r['imagem'] = (f'apps/fatia/receitas/{r["id"]}.jpg'
                       if os.path.exists(os.path.join(fotos, f'{r["id"]}.jpg')) else None)
    for r in receitas:
        for u in r['usa']:
            if u not in ids:
                erros.append(f'{r["id"]}: usa receita inexistente "{u}"')
        for g in r['ingredientes']:
            for it in g['itens']:
                for l in it.get('links', []):
                    if l not in ids:
                        erros.append(f'{r["id"]}: link inexistente "{l}"')
                if it.get('item') and it['item'] not in INGREDIENTE_POR_ID:
                    erros.append(f'{r["id"]}: ingrediente desconhecido "{it["item"]}"')
    if erros:
        raise ErroReceitas('Erros nas receitas:\n' + '\n'.join(erros))
    return receitas


RECEITAS = ler_receitas()
POR_ID = {r['id']: r for r in RECEITAS}
RECEITAS_DE_VENDA = [r for r in RECEITAS if r['categoria'] in CATEGORIAS_DE_VENDA]


def receita(rid: str):
    return POR_ID.get(rid)


def sem_acento(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn').lower().strip()


def _simplificar(s: str) -> str:
    s = sem_acento(s)
    s = re.sub(r'\s*\(.*\)$', '', s)
    s = re.sub(r'\bmeio amarga\b', 'meio amargo', s)
    return s.strip()


# Coberturas primeiro: nas versões das fatias, "Ganache meio amarga" é a de cobertura, não a de recheio.
_BASES = sorted((r for r in RECEITAS if r['categoria'] not in CATEGORIAS_DE_VENDA),
                key=lambda r: r['categoria'] != 'coberturas')


def base_citada(texto: str):
    """Receita-base citada pelo nome num texto ('Massa Black', 'Ganache meio amarga')."""
    t = _simplificar(texto)
    t2 = re.sub(r'^massa ', 'massa de ', t)
    for b in _BASES:
        nb = _simplificar(b['nome'])
        if nb == t or nb == t2:
            return b
    return None


def itens_da_receita(rid: str, visitados: set | None = None) -> list[dict]:
    """Ingredientes com quantidade, incluindo os das receitas-base usadas (cada base uma vez só)."""
    visitados = set() if visitados is None else visitados
    r = POR_ID.get(rid)
    if not r or rid in visitados:
        return []
    visitados.add(rid)
    proprios = [{'item': i['item'], 'qtd': i['qtd']}
                for g in r['ingredientes'] for i in g['itens'] if i.get('item') and i.get('qtd')]
    for u in r['usa']:
        proprios += itens_da_receita(u, visitados)
    return proprios


_RE_IGNORAR = re.compile(r'água|veja a receita', re.I)


def outros_ingredientes(rid: str) -> list[str]:
    """Ingredientes sem quantidade (decoração etc.), para lembrar na lista de compras."""
    r = POR_ID.get(rid)
    if not r:
        return []
    return [i['texto'] for g in r['ingredientes'] for i in g['itens']
            if not i.get('item') and not i.get('links') and not _RE_IGNORAR.search(i['texto'])]


def resumo(r: dict) -> dict:
    return {'id': r['id'], 'nome': r['nome'], 'categoria': r['categoria'], 'imagem': r.get('imagem'),
            'dificuldade': r.get('dificuldade'), 'fatias': r.get('fatias'), 'unidade': r.get('unidade')}


def receita_custo(r: dict) -> dict:
    """O que a calculadora e a lista de compras precisam de uma receita de venda."""
    soma: dict[str, float] = {}
    for it in itens_da_receita(r['id']):
        soma[it['item']] = soma.get(it['item'], 0) + it['qtd']
    outros = []
    for rid in [r['id'], *r['usa']]:
        for o in outros_ingredientes(rid):
            if o not in outros:
                outros.append(o)
    return {**resumo(r), 'itens': [{'item': k, 'qtd': v} for k, v in soma.items()], 'outros': outros}


def usadas_por(rid: str) -> list[dict]:
    """Receitas de venda que usam esta base (campo usa:)."""
    return [r for r in RECEITAS if rid in r['usa']]
