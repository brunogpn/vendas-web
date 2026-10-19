"""Regras do produto Música que não dependem de nada externo (testáveis isoladas)."""
import re
from datetime import datetime, timedelta

from musica.dominio.modelos import PedidoGeracao


def montar_geracao(respostas: dict, titulo: str, letra_suno: str, tabela_estilos: dict) -> PedidoGeracao:
    """Junta estilo + clima + voz (conteudo/estilos.json) no pedido para o gerador."""
    voz = tabela_estilos['voz'].get(respostas.get('voz'), tabela_estilos['voz']['feminina'])
    partes = [
        tabela_estilos['estilos'].get(respostas.get('estilo'), tabela_estilos['estilos']['pop']),
        tabela_estilos['clima'].get(respostas.get('clima'), tabela_estilos['clima']['emocionante']),
        voz['texto'],
    ]
    return PedidoGeracao(titulo=titulo or 'Música de presente', letra=letra_suno, estilo=', '.join(partes),
                         genero_vocal=voz['genero_vocal'], negativo=tabela_estilos['negativo'])


def para_quem(respostas: dict) -> str:
    """Como chamar quem recebe: o apelido, se tiver; senão o nome."""
    return (respostas or {}).get('apelido') or (respostas or {}).get('nome') or 'quem você ama'


def para_leitura(letra_texto: str) -> str:
    """Tira as marcações do Suno ([Verse 1], [Chorus]...) para a cliente ler; o refrão vira a linha '(Refrão)'."""
    linhas = []
    for linha in (letra_texto or '').splitlines():
        marcacao = re.fullmatch(r'\s*\[([^\]]+)\]\s*', linha)
        if not marcacao:
            linhas.append(linha)
        elif 'chorus' in marcacao.group(1).lower() and 'pre' not in marcacao.group(1).lower():
            linhas.append('(Refrão)')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(linhas)).strip()


def inicio_previa(duracao_total: float | None, segundos: int) -> float:
    """A prévia começa perto do primeiro refrão (35 s); em música curta, termina no fim."""
    duracao_total = duracao_total or 0
    return 35 if duracao_total >= 35 + segundos else max(0, duracao_total - segundos)


def travou(gerando_desde: datetime | None, agora: datetime, minutos: int) -> bool:
    return bool(gerando_desde) and agora - gerando_desde > timedelta(minutes=minutos)


def validar_presente(nome: str, email: str, quando: datetime | None, agora: datetime) -> str | None:
    """Erro (texto para a cliente) da entrega por e-mail, ou None. `quando` None = enviar agora."""
    if not nome:
        return 'Coloque o nome de quem vai receber.'
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email or ''):
        return 'Confira o e-mail de quem vai receber.'
    if quando and (quando < agora - timedelta(minutes=5) or quando > agora + timedelta(days=90)):
        return 'Escolha um horário a partir de agora, em até 90 dias.'
    return None
