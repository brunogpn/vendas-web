"""Configuração de um app (um arquivo config.py por app, ex.: apps/fatia/config.py).

Aqui fica só o que é do app em si (nome, cores, suporte). O que se VENDE (preço, dias, bônus,
renovação) são os planos dos produtos, cadastrados no admin ("Planos e entregáveis") — ver docs/PLANOS.md.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    slug: str                       # parte da URL: /app/<slug>/ (e prefixo das tabelas app_<slug>_)
    nome: str                       # 'App Fatias'
    nome_curto: str                 # nome embaixo do ícone na tela inicial
    descricao: str
    # Domínio oficial (sem https://). O ícone instalado e o cookie de sessão ficam presos ao
    # domínio, então todo link para o app (Estante, e-mail, checkout) usa este. Vazio = o mesmo
    # domínio de quem chamou (útil no dev).
    dominio: str
    email_suporte: str
    # Remetente dos e-mails do app (código de login, avisos). Precisa estar em "Enviar e-mail
    # como" do Gmail do admin@ (ver CLAUDE.md), senão o Gmail troca pelo admin@.
    email_remetente: str
    nome_remetente: str
    cor_tema: str                   # barra do navegador / splash do PWA
    cor_fundo: str
    cor_botao_email: str            # botão dos e-mails
    # False = piloto: o app só é oferecido no endereço de piloto da landing (ex.: /fatia-e-piloto);
    # a landing dos anúncios e o cross-sell da Estante não o mostram. Quem comprou usa normalmente.
    publico: bool = False
    # Ícones do PWA, relativos a /static/ (192 e 512 px).
    icone_192: str = ''
    icone_512: str = ''

    @property
    def prefixo(self) -> str:
        return f'/app/{self.slug}'
