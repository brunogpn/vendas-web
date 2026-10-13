"""Configuração do App Fatias (/app/fatia/).

Os produtos que vendem o app (Plano Guiado, renovações) são cadastrados no admin como produto do
tipo app (tabela apps_produto). Valores marcados PENDENTE dependem de decisão do Leo e do Bruno.
"""
import os

from apps._nucleo.config_base import AppConfig

CONFIG = AppConfig(
    slug='fatia',
    nome='App Fatias',
    nome_curto='Fatias',
    descricao='Seu passo a passo para vender fatias de bolo',
    # PENDENTE: domínio oficial do app. Por variável de ambiente porque o dev roda em localhost.
    dominio=os.getenv('APP_FATIA_DOMINIO', '').strip(),
    # As respostas caem na fila de atendimento por e-mail (/admin/atendimento-email).
    email_suporte='admin@lsnlivros.com.br',
    email_remetente='admin@lsnlivros.com.br',
    nome_remetente='App Fatias · Ju Negreiros',
    cor_tema='#fafaf8',
    cor_fundo='#fafaf8',
    cor_botao_email='#c4402a',
    # PENDENTE: ícones definitivos (o Bruno ainda vai mandar).
    icone_192='apps/fatia/icone-192.png',
    icone_512='apps/fatia/icone-512.png',
)
