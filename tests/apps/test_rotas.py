"""Rotas do App Fatias num Flask mínimo (só os blueprints dos apps), com sessão e banco falsos."""
import datetime

import pytest
from flask import Flask

import apps
from apps._nucleo import auth, licenca as lic
from apps.fatia import dados

HOJE = datetime.date(2026, 10, 12)
ORIGEM = {'Origin': 'http://localhost'}


@pytest.fixture
def cliente_http(monkeypatch):
    estado = {'cliente': None, 'licenca': None, 'salvos': []}
    monkeypatch.setattr(auth, 'cliente_da_sessao', lambda token: estado['cliente'] if token else None)
    monkeypatch.setattr(lic, 'buscar_licenca', lambda cid, slug: estado['licenca'])
    monkeypatch.setattr(lic, 'registrar_acesso', lambda cid, slug: None)
    monkeypatch.setattr(lic.datas, 'hoje', lambda: HOJE)
    monkeypatch.setattr(dados, 'perfil', lambda cid: {**dados.PERFIL_PADRAO, 'onboarding_ok': 1})
    monkeypatch.setattr(dados, 'salvar_lancamento', lambda *a: estado['salvos'].append(a))
    flask_app = Flask(__name__)
    apps.registrar(flask_app)
    c = flask_app.test_client()
    c.set_cookie(auth.COOKIE, 'token-teste', path='/app/')
    return c, estado


def _logar(estado, expira):
    estado['cliente'] = {'id': 1, 'email': 'maria@ex.com', 'nome': 'Maria'}
    estado['licenca'] = {'id': 1, 'cliente_id': 1, 'app_slug': 'fatia', 'expira_em': expira, 'ultimo_acesso_em': None}


def test_sem_sessao_vai_para_entrar(cliente_http):
    c, _ = cliente_http
    r = c.get('/app/fatia/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/app/fatia/entrar')


def test_post_sem_origem_do_site_e_recusado(cliente_http):
    c, estado = cliente_http
    _logar(estado, HOJE)
    r = c.post('/app/fatia/vendas/salvar', json={'data': '2026-10-12'})
    assert r.status_code == 403 and 'recusado' in r.get_json()['erro']


def test_post_sem_sessao_pede_para_entrar(cliente_http):
    c, _ = cliente_http
    r = c.post('/app/fatia/vendas/salvar', json={}, headers=ORIGEM)
    assert r.status_code == 401 and r.get_json()['entrar'] is True


def test_licenca_vencida_nao_grava_venda(cliente_http):
    c, estado = cliente_http
    _logar(estado, HOJE - datetime.timedelta(days=1))
    r = c.post('/app/fatia/vendas/salvar', json={'data': '2026-10-12', 'fatias': 3}, headers=ORIGEM)
    assert r.status_code == 403 and r.get_json()['erro'] == auth.MSG_LICENCA_VENCIDA
    assert estado['salvos'] == []


def test_venda_no_futuro_e_recusada(cliente_http):
    c, estado = cliente_http
    _logar(estado, HOJE + datetime.timedelta(days=30))
    r = c.post('/app/fatia/vendas/salvar', json={'data': '2026-10-13', 'fatias': 3}, headers=ORIGEM)
    assert r.status_code == 400 and estado['salvos'] == []


def test_cliente_sem_licenca_deste_app(cliente_http):
    c, estado = cliente_http
    estado['cliente'] = {'id': 1, 'email': 'maria@ex.com', 'nome': 'Maria'}
    r = c.get('/app/fatia/')
    assert r.status_code == 403 and 'ainda não tem' in r.get_data(as_text=True)


def test_manifest_e_service_worker_no_escopo_do_app(cliente_http):
    c, _ = cliente_http
    m = c.get('/app/fatia/manifest.webmanifest').get_json(force=True)
    assert m['scope'] == '/app/fatia/' and m['start_url'] == '/app/fatia/' and m['display'] == 'standalone'
    assert c.get('/app/fatia/sw.js').status_code == 200
    assert c.get('/app/nao-existe/sw.js').status_code == 404


def test_numero_grande_demais_vira_mensagem_e_nao_erro_do_banco(cliente_http):
    c, estado = cliente_http
    _logar(estado, HOJE + datetime.timedelta(days=30))
    r = c.post('/app/fatia/vendas/salvar', json={'data': '2026-10-12', 'gasto': '9.999.999.999', 'fatias': 1},
               headers=ORIGEM)
    assert r.status_code == 400 and 'grande demais' in r.get_json()['erro']
    assert estado['salvos'] == []
