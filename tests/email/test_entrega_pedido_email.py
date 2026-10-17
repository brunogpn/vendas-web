"""
E-mail de entrega das vendas do site: o link enviado é o da Estante 2 (/pedido2/<guid>), a mesma
para onde o checkout redireciona depois do pagamento.
"""
import database
from fluxos import entrega_pedido_email


def test_entrega_por_email_manda_link_da_estante_2(monkeypatch):
    enviados = []
    monkeypatch.setenv('APP_BASE_URL', 'https://lsnlivros.com.br/')
    monkeypatch.setattr(database, 'get_pedido', lambda i: {
        'id': i, 'produto_id': 12, 'email': 'cliente@x.com', 'contact_name': 'Maria Silva',
        'data_envio_ebook': None})
    monkeypatch.setattr(database, 'get_produto_disponivel_web', lambda i: {'nome': 'Fatia de Bolo'})
    monkeypatch.setattr(database, 'listar_itens_pedido', lambda i: [{'nome': 'Fatia de Bolo', 'tipo': 'principal'}])
    monkeypatch.setattr(database, 'garantir_guid_pedido', lambda i: 'abc123')
    monkeypatch.setattr(database, 'marcar_ebook_enviado', lambda i: None)
    monkeypatch.setattr(database, 'definir_gmail_thread_pedido', lambda *a: None)
    monkeypatch.setattr(database, 'salvar_mensagem_email_pedido', lambda **k: None)
    monkeypatch.setattr(entrega_pedido_email, 'rotular_enviado', lambda *a: None)
    monkeypatch.setattr(entrega_pedido_email, '_enviar_gmail', lambda **k: enviados.append(k) or {'id': 'm1'})
    import apps
    monkeypatch.setattr(apps, 'apps_do_pedido', lambda i: [])  # Básico: só e-books

    entrega_pedido_email.executar(7)

    html = enviados[0]['html']
    assert 'https://lsnlivros.com.br/pedido2/abc123' in html
    assert '/pedido/abc123' not in html
    assert 'abrir-app' not in html
    assert 'Pronto para baixar' in enviados[0]['subject']


def test_entrega_de_plano_com_app_leva_botao_do_app(monkeypatch):
    enviados = []
    monkeypatch.setenv('APP_BASE_URL', 'https://lsnlivros.com.br/')
    monkeypatch.setattr(database, 'get_pedido', lambda i: {
        'id': i, 'produto_id': 16, 'email': 'cliente@x.com', 'contact_name': 'Maria Silva',
        'data_envio_ebook': None})
    monkeypatch.setattr(database, 'get_produto_disponivel_web', lambda i: {'nome': 'App Fatias — Plano Guiado'})
    monkeypatch.setattr(database, 'listar_itens_pedido', lambda i: [{'nome': 'App Fatias — Plano Guiado', 'tipo': 'principal'},
                                                                   {'nome': 'Fatias que Vendem', 'tipo': 'bonus'}])
    monkeypatch.setattr(database, 'garantir_guid_pedido', lambda i: 'abc123')
    monkeypatch.setattr(database, 'marcar_ebook_enviado', lambda i: None)
    monkeypatch.setattr(database, 'definir_gmail_thread_pedido', lambda *a: None)
    monkeypatch.setattr(database, 'salvar_mensagem_email_pedido', lambda **k: None)
    monkeypatch.setattr(entrega_pedido_email, 'rotular_enviado', lambda *a: None)
    monkeypatch.setattr(entrega_pedido_email, '_enviar_gmail', lambda **k: enviados.append(k) or {'id': 'm1'})
    import apps
    monkeypatch.setattr(apps, 'apps_do_pedido', lambda i: [(apps.APPS['fatia'], 90)] if i == 8 else [])

    entrega_pedido_email.executar(8)

    html = enviados[0]['html']
    assert 'https://lsnlivros.com.br/pedido2/abc123/abrir-app/fatia' in html
    assert 'Abrir meu App Fatias' in html
    assert 'https://lsnlivros.com.br/pedido2/abc123' in html  # a Estante continua (e-books bônus)
    assert 'Seu acesso está liberado' in enviados[0]['subject']


def test_entrega_cita_todos_os_principais_do_plano(monkeypatch):
    """Completo = app + e-book: o resumo diz que ela comprou os dois."""
    enviados = []
    monkeypatch.setenv('APP_BASE_URL', 'https://lsnlivros.com.br/')
    monkeypatch.setattr(database, 'get_pedido', lambda i: {
        'id': i, 'produto_id': 12, 'email': 'cliente@x.com', 'contact_name': 'Maria Silva', 'data_envio_ebook': None})
    monkeypatch.setattr(database, 'get_produto_disponivel_web', lambda i: {'nome': 'Fatia de Bolo'})
    monkeypatch.setattr(database, 'listar_itens_pedido', lambda i: [{'nome': 'App Fatias', 'tipo': 'principal'},
                                                                   {'nome': 'Fatias que Vendem', 'tipo': 'principal'}])
    monkeypatch.setattr(database, 'garantir_guid_pedido', lambda i: 'abc123')
    monkeypatch.setattr(database, 'marcar_ebook_enviado', lambda i: None)
    monkeypatch.setattr(database, 'definir_gmail_thread_pedido', lambda *a: None)
    monkeypatch.setattr(database, 'salvar_mensagem_email_pedido', lambda **k: None)
    monkeypatch.setattr(entrega_pedido_email, 'rotular_enviado', lambda *a: None)
    monkeypatch.setattr(entrega_pedido_email, '_enviar_gmail', lambda **k: enviados.append(k) or {'id': 'm1'})
    import apps
    monkeypatch.setattr(apps, 'apps_do_pedido', lambda i: [])
    entrega_pedido_email.executar(9)
    assert 'você comprou <strong>App Fatias e Fatias que Vendem</strong>' in enviados[0]['html']
