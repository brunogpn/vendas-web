import datetime
from contextlib import contextmanager

import pytest

import apps
from apps._nucleo import licenca as lic
from apps._nucleo.config_base import AppConfig

HOJE = datetime.date(2026, 10, 12)


def test_nova_expiracao_soma_do_vencimento_ou_de_hoje():
    assert lic.nova_expiracao(None, 90, HOJE) == HOJE + datetime.timedelta(days=90)
    # renovou antes de vencer: soma a partir do vencimento
    assert lic.nova_expiracao('2026-10-20', 30, HOJE) == datetime.date(2026, 11, 19)
    # vence hoje ainda conta como ativa: soma a partir de hoje (o próprio vencimento)
    assert lic.nova_expiracao(HOJE, 10, HOJE) == HOJE + datetime.timedelta(days=10)
    # já venceu: a partir de hoje
    assert lic.nova_expiracao('2026-09-01', 30, HOJE) == HOJE + datetime.timedelta(days=30)


def test_licenca_ativa_no_dia_do_vencimento(monkeypatch):
    monkeypatch.setattr(lic.datas, 'hoje', lambda: HOJE)
    assert lic.licenca_ativa({'expira_em': HOJE})
    assert not lic.licenca_ativa({'expira_em': HOJE - datetime.timedelta(days=1)})
    assert lic.dias_restantes({'expira_em': HOJE}) == 0
    assert not lic.licenca_ativa(None)


@pytest.fixture
def app_teste(monkeypatch):
    import database
    cfg = AppConfig(slug='teste', nome='App Teste', nome_curto='T', descricao='', dominio='', email_suporte='s@x',
                    email_remetente='s@x', nome_remetente='T', cor_tema='#fff', cor_fundo='#fff',
                    cor_botao_email='#000')
    monkeypatch.setattr(apps, 'APPS', {'teste': cfg})
    monkeypatch.setattr(lic, 'APPS', {'teste': cfg})
    # Pedidos do plano com o app "teste" (90 dias): os de produto 77. Os outros não têm item app.
    monkeypatch.setattr(lic, 'apps_do_pedido', lambda pid: [(cfg, 90)] if int(pid) in (10, 1, 3, 4) else [])
    return cfg


def test_apps_do_pedido_vem_dos_itens_app_com_os_dias_do_plano(monkeypatch):
    import database
    cfg = AppConfig(slug='teste', nome='App Teste', nome_curto='T', descricao='', dominio='', email_suporte='s@x',
                    email_remetente='s@x', nome_remetente='T', cor_tema='#fff', cor_fundo='#fff',
                    cor_botao_email='#000')
    monkeypatch.setattr(apps, 'APPS', {'teste': cfg})
    consultas = []
    linhas = [{'app_slug': 'teste', 'dias': 90}, {'app_slug': 'desligado', 'dias': 30}, {'app_slug': 'teste', 'dias': None}]
    monkeypatch.setattr(database.db, 'execute_query', lambda sql, p=None, **k: consultas.append(p) or linhas)
    assert apps.apps_do_pedido(10) == [(cfg, 90)]   # app fora de APPS e item sem dias ficam de fora
    assert consultas == [(10,)]


class CursorFalso:
    def __init__(self, banco):
        self.banco, self.rowcount, self.lastrowid, self._um = banco, 0, None, None

    def execute(self, sql, params=()):
        self.banco.sqls.append(sql)
        if sql.startswith('INSERT INTO apps_clientes'):
            self.lastrowid = 5
        elif sql.startswith('INSERT IGNORE INTO apps_licenca_pedidos'):
            ja = params[0] in self.banco.pedidos_liberados
            self.banco.pedidos_liberados.add(params[0])
            self.rowcount = 0 if ja else 1
        elif sql.startswith('SELECT id, expira_em FROM apps_licencas'):
            self._um = self.banco.licenca
        elif sql.startswith('UPDATE apps_licencas SET expira_em'):
            self.banco.licenca = {'id': 1, 'expira_em': params[0]}
        elif sql.startswith('INSERT INTO apps_licencas'):
            self.banco.licenca = {'id': 1, 'expira_em': params[2]}

    def fetchone(self):
        return self._um


class BancoFalso:
    def __init__(self, pedido):
        self.pedido, self.sqls, self.pedidos_liberados, self.licenca = pedido, [], set(), None

    def execute_query(self, sql, params=None, **kw):
        if sql.startswith('SELECT id, produto_id, email'):
            return self.pedido
        return None

    @contextmanager
    def get_cursor(self):
        yield CursorFalso(self)


def test_liberar_pedido_pago_soma_uma_vez_so(app_teste, monkeypatch):
    banco = BancoFalso({'id': 10, 'produto_id': 77, 'email': ' Maria@Ex.com ', 'contact_name': 'Maria',
                        'estado_id': 1000, 'valor_pago': 22})
    monkeypatch.setattr(lic, 'db', banco)
    monkeypatch.setattr(lic.datas, 'hoje', lambda: HOJE)
    primeira = lic.liberar_licencas_do_pedido(10)
    assert primeira == [{'app_slug': 'teste', 'cliente_id': 5, 'dias': 90, 'expira_em': HOJE + datetime.timedelta(days=90)}]
    # chamada de novo (Estante, retry do Celery, reconciliação): não soma de novo
    assert lic.liberar_licencas_do_pedido(10) == []
    assert banco.licenca['expira_em'] == HOJE + datetime.timedelta(days=90)


@pytest.mark.parametrize('pedido', [
    {'id': 1, 'produto_id': 77, 'email': 'a@b.com', 'contact_name': '', 'estado_id': 1002, 'valor_pago': 0},  # não pago
    {'id': 4, 'produto_id': 77, 'email': 'a@b.com', 'contact_name': '', 'estado_id': 0, 'valor_pago': 22},  # WhatsApp: não libera
    {'id': 2, 'produto_id': 12, 'email': 'a@b.com', 'contact_name': '', 'estado_id': 1000, 'valor_pago': 10},  # Básico: sem app
    {'id': 3, 'produto_id': 77, 'email': '', 'contact_name': '', 'estado_id': 1000, 'valor_pago': 22},  # sem e-mail
])
def test_liberar_ignora_pedido_que_nao_libera(app_teste, monkeypatch, pedido):
    banco = BancoFalso(pedido)
    monkeypatch.setattr(lic, 'db', banco)
    assert lic.liberar_licencas_do_pedido(pedido['id']) == []
    assert not any(s.startswith('INSERT') for s in banco.sqls)


class BancoConta:
    """Para pedido_criou_a_conta: a linha do pedido e as contagens de outras coisas da cliente."""
    def __init__(self, linha, licencas=0, pedidos=0, ajustes=0):
        self.linha, self.outros = linha, {'licencas': licencas, 'pedidos': pedidos, 'ajustes': ajustes}

    def execute_query(self, sql, params=None, **kw):
        return self.linha if sql.startswith('SELECT expira_antes') else self.outros


@pytest.mark.parametrize('banco,esperado', [
    (BancoConta({'expira_antes': None}), True),                       # conta nova, nascida deste pedido
    (BancoConta({'expira_antes': HOJE}), False),                      # renovação: conta já existia
    (BancoConta(None), False),                                        # pedido não liberou esta conta
    (BancoConta({'expira_antes': None}, pedidos=1), False),           # já tinha outro pedido
    (BancoConta({'expira_antes': None}, licencas=1), False),          # já tinha outro app
    (BancoConta({'expira_antes': None}, ajustes=1), False),           # já foi mexida no admin
])
def test_entrada_sem_codigo_so_para_conta_nova(monkeypatch, banco, esperado):
    # Quem compra com o e-mail de outra pessoa não pode entrar, pela Estante, numa conta que já existia.
    monkeypatch.setattr(lic, 'db', banco)
    assert lic.pedido_criou_a_conta(5, 10, 'fatia') is esperado
