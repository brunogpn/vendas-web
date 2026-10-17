"""Configuração do App Fatias (/app/fatia/).

Os planos que vendem o app (Completo/Guiado, renovações) são cadastrados no admin, em "Planos e
entregáveis" do produto, com o App Fatias como item. Valores marcados PENDENTE dependem de decisão do
Leo e do Bruno.
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
    # Lançado em 14/10/2026 (homologado pelo Bruno no piloto): /fatia-e mostra Básico + Plano Guiado e a
    # Estante oferece o app no cross-sell. False = volta ao piloto (planos só em /fatia-e-piloto).
    publico=True,
    # PENDENTE: ícones definitivos (o Bruno ainda vai mandar).
    icone_192='apps/fatia/icone-192.png',
    icone_512='apps/fatia/icone-512.png',
)
