"""Valor da conversão no Google Ads: venda do site manda o valor real pago; WhatsApp, R$ 10 fixo."""
import sys
import types
from types import SimpleNamespace

# O fluxo importa a biblioteca do Google Ads no topo; sem ela instalada, um módulo falso basta para
# testar só a regra do valor (com ela instalada, usa a real e não interfere em outros testes).
try:
    import google.ads.googleads.client  # noqa: F401
except ImportError:
    for nome in ('google.ads', 'google.ads.googleads', 'google.ads.googleads.client'):
        sys.modules.setdefault(nome, types.ModuleType(nome))
    sys.modules['google.ads.googleads.client'].GoogleAdsClient = object

from fluxos.fluxo_upload_google_ads import valor_conversao  # noqa: E402


def v(estado_id, valor_pago, produto_id=12):
    return SimpleNamespace(produto_id=produto_id, estado_id=estado_id, valor_pago=valor_pago)


def test_venda_do_site_manda_o_valor_real_pago():
    assert valor_conversao(v(1000, 22.0)) == '22.00'      # Completo
    assert valor_conversao(v(1000, '28.90')) == '28.90'   # plano + um bump
    assert valor_conversao(v(1000, 10.0)) == '10.00'      # Básico (antes: 20 fixo no produto 12)
    assert valor_conversao(v(1000, 6.9, produto_id=14)) == '6.90'


def test_venda_do_whatsapp_manda_10_fixo():
    # O comprovante do WhatsApp não é validado: o valor digitado pode não ser o pago.
    assert valor_conversao(v(0, 16.9)) == '10.00'
    assert valor_conversao(v(0, 10.0, produto_id=8)) == '10.00'


def test_venda_sem_valor_pago_cai_no_fixo():
    assert valor_conversao(v(1000, None)) == '10.00'
    assert valor_conversao(v(1000, 0)) == '10.00'
    assert valor_conversao(v(1000, 'lixo')) == '10.00'
    assert valor_conversao(SimpleNamespace(produto_id=12, valor_pago=22)) == '10.00'  # sem estado
