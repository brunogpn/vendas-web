"""Os objetos que circulam entre os casos de uso e as portas (sem Flask, sem banco, sem provedor)."""
from dataclasses import dataclass, field

# Caminho de uma música antes do pagamento:
# escrevendo → letra_pronta → gerando → processando → previa_pronta
#     ↘ erro_letra                 ↘ erro (avisa a equipe; a cliente vê "estamos finalizando")
# O pagamento não muda o status: a música paga é a que tem liberada_em (pedido pago).
ESCREVENDO = 'escrevendo'
LETRA_PRONTA = 'letra_pronta'
ERRO_LETRA = 'erro_letra'
GERANDO = 'gerando'
PROCESSANDO = 'processando'
PREVIA_PRONTA = 'previa_pronta'
ERRO = 'erro'

# Resultado de uma geração (o mesmo formato vem de qualquer provedor).
GERACAO_ANDAMENTO = 'gerando'
GERACAO_PRONTA = 'pronto'
GERACAO_FALHOU = 'falhou'


@dataclass(frozen=True)
class PedidoGeracao:
    """O que o gerador recebe para compor a música."""
    titulo: str
    letra: str            # letra com as marcações de estrutura ([Verse], [Chorus]...)
    estilo: str           # gênero, clima e voz em texto
    genero_vocal: str     # 'f' | 'm'
    negativo: str         # o que evitar


@dataclass(frozen=True)
class Faixa:
    url: str              # onde baixar (do provedor; nunca vai para o navegador da cliente)
    duracao: float | None


@dataclass(frozen=True)
class ResultadoGeracao:
    status: str                              # GERACAO_ANDAMENTO | GERACAO_PRONTA | GERACAO_FALHOU
    faixas: list[Faixa] = field(default_factory=list)
    erro: str = ''


@dataclass(frozen=True)
class Letra:
    titulo: str
    letra_exibicao: str
    letra_suno: str
    observacao: str = ''


class ErroGerador(Exception):
    """O gerador recusou ou não respondeu ao pedido de geração."""


class ErroLetra(Exception):
    """A IA não conseguiu escrever a letra (recusa, resposta inválida ou fora do ar)."""


class ErroVideo(Exception):
    """Não deu para montar o videoclipe."""
