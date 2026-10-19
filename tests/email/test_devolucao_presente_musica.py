"""Devolução (DSN) de um presente da Música: quem recusou vem dos campos próprios, não do texto citado."""
import base64

from fluxos.fluxo_email_conversas import _destinatarios_recusados


def _b64(texto):
    return base64.urlsafe_b64encode(texto.encode()).decode()


def test_le_quem_recusou_e_ignora_o_cc_citado():
    citado = ('To: lena@exemplo.com\r\nCc: patricia@exemplo.com\r\nSubject: Patricia fez uma musica para voce')
    full = {'payload': {'mimeType': 'multipart/report', 'parts': [
        {'mimeType': 'text/plain', 'body': {'data': _b64("A mensagem não foi entregue: caixa cheia.\r\n" + citado)}},
        {'mimeType': 'message/delivery-status', 'body': {'data': _b64(
            'Reporting-MTA: dns; googlemail.com\r\n\r\nFinal-Recipient: rfc822; Lena@Exemplo.com\r\n'
            'Action: failed\r\nStatus: 5.2.2\r\n')}},
        {'mimeType': 'message/rfc822', 'body': {'data': _b64(citado)}},
    ]}}
    assert _destinatarios_recusados(full, {}) == ['lena@exemplo.com']


def test_cabecalho_do_gmail():
    assert _destinatarios_recusados({'payload': {}}, {'x-failed-recipients': 'lena@exemplo.com, outro@x.com'}) == \
        ['lena@exemplo.com', 'outro@x.com']


def test_devolucao_que_nao_diz_quem():
    assert _destinatarios_recusados({'payload': {'mimeType': 'text/plain', 'body': {'data': _b64('erro')}}}, {}) == []


def test_aviso_de_atraso_nao_e_devolucao():
    """Greylisting: o Gmail avisa 'Delay' no mesmo thread; a mensagem ainda chega — não pode reenviar o presente."""
    full = {'payload': {'mimeType': 'multipart/report', 'parts': [
        {'mimeType': 'message/delivery-status', 'body': {'data': _b64(
            'Reporting-MTA: dns; googlemail.com\r\n\r\nFinal-Recipient: rfc822; lena@exemplo.com\r\n'
            'Action: delayed\r\nStatus: 4.7.1\r\n')}}]}}
    assert _destinatarios_recusados(full, {}) is None
