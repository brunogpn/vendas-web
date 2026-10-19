"""Onde ficam os arquivos de cada música (pasta privada; o Flask serve só depois de conferir o acesso).

storage/musica/<token>/completa/<n>.mp3   música inteira (só depois de paga)
storage/musica/<token>/previa/<n>.mp3     trecho grátis
storage/musica/<token>/video/             fotos/, letra.ass, videoclipe.mp4, capa.jpg
"""
import re
import shutil
from pathlib import Path


class Arquivos:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)

    def pasta(self, token: str) -> Path:
        if not re.fullmatch(r'[0-9a-f]{32}', token or ''):   # o token vira nome de pasta: nada além de hex
            raise ValueError('token inválido')
        return self.raiz / token

    def completa(self, token: str, numero: int) -> Path:
        return self.pasta(token) / 'completa' / f'{int(numero)}.mp3'

    def previa(self, token: str, numero: int) -> Path:
        return self.pasta(token) / 'previa' / f'{int(numero)}.mp3'

    def pasta_video(self, token: str) -> Path:
        return self.pasta(token) / 'video'

    def videoclipe(self, token: str) -> Path:
        return self.pasta_video(token) / 'videoclipe.mp4'

    def capa_video(self, token: str) -> Path:
        return self.pasta_video(token) / 'capa.jpg'

    def apagar(self, token: str) -> None:
        shutil.rmtree(self.pasta(token), ignore_errors=True)
