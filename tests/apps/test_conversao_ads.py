"""Valor da conversão no Google Ads: produto de app manda o valor real pago; os demais, a regra fixa."""
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

APPS = {16}


def v(produto_id, valor_pago):
    return SimpleNamespace(produto_id=produto_id, valor_pago=valor_pago)


def test_produto_app_manda_o_valor_real_pago():
    assert valor_conversao(v(16, 22.0), APPS) == '22.00'
    assert valor_conversao(v(16, '28.90'), APPS) == '28.90'  # Guiado + um bump


def test_produtos_de_ebook_continuam_com_a_regra_fixa():
    assert valor_conversao(v(12, 10.0), APPS) == '20.00'
    assert valor_conversao(v(8, 16.9), APPS) == '10.00'


def test_app_sem_valor_pago_cai_na_regra_fixa():
    assert valor_conversao(v(16, None), APPS) == '10.00'
    assert valor_conversao(v(16, 0), APPS) == '10.00'
