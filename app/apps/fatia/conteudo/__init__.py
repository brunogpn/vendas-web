"""Conteúdo do App Fatias (vindo do projeto do Bruno): trilha, ingredientes e receitas.

- trilha.json: fases e os 38 passos. A ORDEM da lista é a que vale (um passo libera o próximo);
  os ids não seguem a ordem e NUNCA podem ser renumerados (as tarefas concluídas ficam gravadas
  pelo id). Passo novo recebe o próximo id livre.
- ingredientes.json: catálogo usado no custo e na lista de compras (a ordem é a da lista de compras).
- receitas/*.txt: ver receitas/LEIAME.md e apps/fatia/receitas.py.
"""
import json
import os

_PASTA = os.path.dirname(__file__)


def _ler(nome):
    with open(os.path.join(_PASTA, nome), encoding='utf-8') as f:
        return json.load(f)


_trilha = _ler('trilha.json')
FASES: list[dict] = _trilha['fases']
PASSOS: list[dict] = _trilha['passos']
TOTAL_PASSOS = len(PASSOS)
PASSO_POR_ID = {p['id']: p for p in PASSOS}
POSICAO = {p['id']: i for i, p in enumerate(PASSOS)}  # id → posição na ordem da trilha
FASE_POR_NUMERO = {f['numero']: f for f in FASES}

_ing = _ler('ingredientes.json')
GRUPOS_INGREDIENTES: list[str] = _ing['grupos']
INGREDIENTES: list[dict] = _ing['ingredientes']
INGREDIENTE_POR_ID = {i['id']: i for i in INGREDIENTES}

assert len(PASSO_POR_ID) == TOTAL_PASSOS, 'id de passo repetido em trilha.json'
