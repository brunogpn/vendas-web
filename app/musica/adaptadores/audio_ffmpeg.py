"""Audio com requests + ffmpeg: baixa a música pronta e corta o trecho da prévia.

A música completa fica na pasta privada e só é servida depois do pagamento; o link do provedor
nunca vai para o navegador da cliente.
"""
import shutil
import subprocess
from pathlib import Path

import requests

from musica.adaptadores.gerador_simulado import URL_SIMULADA

FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'


class AudioFfmpeg:
    def baixar(self, url: str, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix('.tmp')
        if url == URL_SIMULADA:
            # Música de teste: um tom simples de 2min30, só para o fluxo funcionar.
            subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=330:duration=150',
                            '-b:a', '128k', '-f', 'mp3', str(temporario)], check=True)
        else:
            with requests.get(url, stream=True, timeout=120) as resposta:
                resposta.raise_for_status()
                with open(temporario, 'wb') as arquivo:
                    for pedaco in resposta.iter_content(chunk_size=1 << 16):
                        arquivo.write(pedaco)
        temporario.replace(destino)   # nunca fica um MP3 pela metade no lugar do certo

    def cortar_previa(self, origem: Path, destino: Path, inicio: float, segundos: int) -> None:
        """Corta `segundos` a partir de `inicio`, com fade no começo e no fim."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        filtro = f'afade=t=in:d=1,afade=t=out:st={segundos - 3}:d=3'
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', str(inicio), '-t', str(segundos), '-i', str(origem),
                        '-af', filtro, '-b:a', '96k', str(destino)], check=True)
