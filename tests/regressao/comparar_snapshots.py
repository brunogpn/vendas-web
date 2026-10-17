"""Compara dois retratos de snapshot_checkout.py e mostra só o que mudou.

    python3 tests/regressao/comparar_snapshots.py antes.json depois.json [--ignorar regex ...]

Linhas de HTML que casam com algum --ignorar (ex.: mudanças esperadas) não contam como diferença.
Sai com código 1 se houver diferença.
"""
import difflib
import json
import re
import sys


def achatar(obj, prefixo=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from achatar(v, f'{prefixo}/{k}')
    elif isinstance(obj, list):
        yield prefixo, json.dumps(obj, ensure_ascii=False, sort_keys=True)
    else:
        yield prefixo, obj


def main():
    args = sys.argv[1:]
    ignorar = []
    if '--ignorar' in args:
        i = args.index('--ignorar')
        ignorar = [re.compile(x) for x in args[i + 1:]]
        args = args[:i]
    antes, depois = (dict(achatar(json.load(open(a)))) for a in args)
    diferencas = 0
    for chave in sorted(set(antes) | set(depois)):
        a, d = antes.get(chave), depois.get(chave)
        if a == d:
            continue
        if isinstance(a, str) and isinstance(d, str) and '\n' in (a + d):
            linhas = [l for l in difflib.unified_diff(a.splitlines(), d.splitlines(), lineterm='', n=0)
                      if l[:1] in '+-' and l[:3] not in ('+++', '---')]
            linhas = [l for l in linhas if not any(r.search(l) for r in ignorar)]
            if not linhas:
                continue
            diferencas += 1
            print(f'\n### {chave}')
            for l in linhas[:40]:
                print('   ', l[:220])
        else:
            diferencas += 1
            print(f'\n### {chave}\n    antes : {a}\n    depois: {d}')
    print(f'\n{diferencas} diferença(s).')
    sys.exit(1 if diferencas else 0)


main()
