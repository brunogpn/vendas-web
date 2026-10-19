"""Legenda do videoclipe: encaixa as linhas da NOSSA letra (que está certa) nos tempos das palavras que a
transcrição ouviu, sempre andando para a frente na música, e gera o arquivo .ass que o ffmpeg queima no vídeo.

A transcrição em si é um adaptador (adaptadores/transcritor_openai.py); aqui só a regra.
"""
import difflib
import re
import unicodedata


def _normalizar(palavra):
    sem_acento = unicodedata.normalize("NFD", palavra.lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", sem_acento)


def linhas_da_letra(letra_suno):
    """Linhas cantadas, sem as marcações [Verse], sem linhas vazias e sem parênteses de coro."""
    linhas = []
    for linha in (letra_suno or "").splitlines():
        linha = linha.strip()
        if not linha or re.fullmatch(r"\[[^\]]*\]", linha):
            continue
        linha = re.sub(r"\(([^)]*)\)", r"\1", linha).strip()   # coro entre parênteses vira texto normal
        if linha:
            linhas.append(linha)
    return linhas


def alinhar(linhas, palavras, janela=40):
    """Para cada linha da letra, acha o trecho da transcrição mais parecido. Devolve [(inicio, fim, texto)]."""
    transcritas = [_normalizar(p["palavra"]) for p in palavras]
    resultado, posicao = [], 0
    for linha in linhas:
        alvo = [p for p in (_normalizar(x) for x in linha.split()) if p]
        if not alvo:
            continue
        melhor, melhor_nota = None, 0.0
        for inicio in range(posicao, min(len(palavras), posicao + janela)):
            trecho = transcritas[inicio:inicio + len(alvo)]
            nota = difflib.SequenceMatcher(None, " ".join(alvo), " ".join(trecho)).ratio()
            if nota > melhor_nota:
                melhor, melhor_nota = inicio, nota
        if melhor is None or melhor_nota < 0.45:
            continue   # não achou com segurança: essa linha fica sem legenda
        fim = min(len(palavras), melhor + len(alvo)) - 1
        resultado.append([palavras[melhor]["inicio"], palavras[fim]["fim"], linha])
        posicao = fim + 1
    # Cada legenda fica na tela até a próxima começar (no máximo 2s depois do fim cantado).
    for i, item in enumerate(resultado):
        proximo = resultado[i + 1][0] if i + 1 < len(resultado) else item[1] + 2
        item[1] = max(item[0] + 0.8, min(proximo - 0.05, item[1] + 2.0))
    return [tuple(x) for x in resultado]


def _tempo_ass(segundos):
    h, resto = divmod(max(0, segundos), 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def gerar_ass(legendas, destino, deslocamento=0.0, largura=720, altura=1280):
    """Arquivo .ass: letra branca, em negrito, com contorno e sombra, na parte de baixo do vídeo."""
    cabecalho = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Letra,Figtree,60,&H00FFFFFF,&H00FFFFFF,&H50000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = "".join(
        f"Dialogue: 0,{_tempo_ass(a + deslocamento)},{_tempo_ass(b + deslocamento)},Letra,,0,0,0,,{{\\fad(150,150)}}{texto.replace('{', '').replace('}', '')}\n"
        for a, b, texto in legendas
    )
    with open(destino, "w", encoding="utf-8") as f:
        f.write(cabecalho + eventos)
