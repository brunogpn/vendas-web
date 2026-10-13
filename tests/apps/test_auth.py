import datetime

import pytest

from apps._nucleo import auth

AGORA = datetime.datetime(2026, 10, 12, 10, 0)


class Banco:
    """Banco falso para o login: guarda o código e conta pedidos."""
    def __init__(self, cliente=True, por_email=0, por_ip=0):
        self.cliente = {'id': 3, 'email': 'maria@ex.com', 'nome': 'Maria'} if cliente else None
        self.contagem = {'por_email': por_email, 'por_ip': por_ip}
        self.codigo = None
        self.sqls = []

    def execute_query(self, sql, params=None, **kw):
        self.sqls.append(sql)
        if 'FROM apps_pedidos_codigo' in sql:
            return self.contagem
        if sql.startswith('UPDATE apps_codigos_login SET tentativas'):
            # reserva atômica: só conta se ainda não estourou nem venceu
            email, maximo, agora = params
            c = self.codigo
            if c and c['tentativas'] < maximo and c['expira_em'] > agora:
                c['tentativas'] += 1
                return 1
            return 0
        if sql.startswith('SELECT expira_em, tentativas'):
            return self.codigo
        if sql.startswith('DELETE FROM apps_codigos_login WHERE email = %s AND codigo_hash'):
            if self.codigo and self.codigo['codigo_hash'] == params[1]:
                self.codigo = None
                return 1
            return 0

    def get_cursor(self):
        banco = self

        class C:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def execute(s, sql, params=()):
                banco.sqls.append(sql)
                if sql.startswith('INSERT INTO apps_codigos_login'):
                    banco.codigo = {'codigo_hash': params[1], 'expira_em': params[2], 'tentativas': 0}
        return C()


@pytest.fixture
def banco(monkeypatch):
    def fazer(**kw):
        b = Banco(**kw)
        monkeypatch.setattr(auth, 'db', b)
        monkeypatch.setattr(auth.lic, 'buscar_cliente_por_email', lambda e: b.cliente if b.cliente and e == 'maria@ex.com' else None)
        monkeypatch.setattr(auth.datas, 'agora', lambda: AGORA)
        return b
    return fazer


def test_pedir_codigo_valida_email_e_cliente(banco):
    banco()
    assert 'incompleto' in auth.pedir_codigo('maria', '1.1.1.1')['erro']
    assert 'Não encontramos' in auth.pedir_codigo('outra@ex.com', '1.1.1.1')['erro']


def test_pedir_codigo_limites_por_email_e_por_ip(banco):
    banco(por_email=5)
    assert 'vários códigos' in auth.pedir_codigo('maria@ex.com', '1.1.1.1')['erro']
    banco(por_ip=20)
    assert 'deste aparelho' in auth.pedir_codigo('maria@ex.com', '1.1.1.1')['erro']


def test_codigo_gravado_so_como_hash_e_confere(banco):
    b = banco()
    r = auth.pedir_codigo('  Maria@Ex.com ', '1.1.1.1')
    assert r['ok'] and len(r['codigo']) == 6 and r['codigo'].isdigit()
    assert r['codigo'] not in b.codigo['codigo_hash']
    assert b.codigo['expira_em'] == AGORA + datetime.timedelta(minutes=15)
    cid, erro = auth.confirmar_codigo('maria@ex.com', r['codigo'][:3] + ' ' + r['codigo'][3:])
    assert cid == 3 and erro is None
    assert b.codigo is None  # usado uma vez só


def test_codigo_errado_conta_tentativas_ate_bloquear(banco):
    b = banco()
    r = auth.pedir_codigo('maria@ex.com', None)
    errado = '000000' if r['codigo'] != '000000' else '111111'
    for _ in range(5):
        assert auth.confirmar_codigo('maria@ex.com', errado) == (None, 'Código errado. Confira os 6 números no seu email.')
    # a 6ª tentativa nem confere o código — mesmo o certo é recusado
    assert auth.confirmar_codigo('maria@ex.com', r['codigo']) == (None, 'Muitas tentativas. Peça um código novo.')
    assert b.codigo['tentativas'] == 5


def test_codigo_vencido(banco):
    b = banco()
    r = auth.pedir_codigo('maria@ex.com', None)
    b.codigo['expira_em'] = AGORA - datetime.timedelta(seconds=1)
    assert auth.confirmar_codigo('maria@ex.com', r['codigo'])[1] == 'Esse código venceu. Peça um código novo.'


def test_codigo_certo_so_vale_uma_vez(banco):
    b = banco()
    r = auth.pedir_codigo('maria@ex.com', None)
    assert auth.confirmar_codigo('maria@ex.com', r['codigo'])[0] == 3
    assert auth.confirmar_codigo('maria@ex.com', r['codigo']) == (None, 'Esse código venceu. Peça um código novo.')
