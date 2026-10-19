"""Rotas da Música (/musica/...): HTTP fino → casos de uso. Erros sempre jsonify(...), 4xx — nunca abort()
(o handler global transforma em 500 e avisa no WhatsApp). POST que grava exige Origin/Referer do próprio host.

Páginas: /musica/ (landing, ?ocasiao=), /musica/criar (quiz), /musica/p/<token> (letra, espera e prévia),
/musica/compra/<guid> (quem comprou), /musica/m/<token> (o presente: QR code e e-mail apontam para cá).
"""
import logging
import re
from pathlib import Path

import requests
from flask import Blueprint, jsonify, make_response, redirect, render_template, request, send_file, url_for

from apps._nucleo.formato import reais
from musica import casos_de_uso as uc
from musica import config
from musica.casos_de_uso import Recusa
from musica.dominio import regras
from musica.dominio.quiz import CHAVES_VALIDAS, FEMININO, MASCULINO, PERGUNTAS
from musica.dominio.recursos import ENTREGA_EMAIL, QRCODE, VIDEOCLIPE
from musica.fabrica import servicos

logger = logging.getLogger(__name__)

bp = Blueprint('musica', __name__, url_prefix='/musica', template_folder='templates', static_folder='static',
               static_url_path='/static')

ATUALIZADO_LEGAL = '17 de outubro de 2026'


# ================================================================ utilidades

def _ip():
    return (request.headers.get('X-Real-IP') or request.remote_addr or '').strip()


def _host():
    return (request.headers.get('X-Forwarded-Host') or request.host or '').split(':')[0].lower()


def _origem_confiavel():
    from apps._nucleo.auth import origem_confiavel
    return origem_confiavel()


def _recusa(r: Recusa):
    return jsonify(erro=r.mensagem), r.status


def _nao_encontrada():
    return render_template('musica/legal.html', pagina='nao_encontrada', atualizado=ATUALIZADO_LEGAL), 404


def _turnstile_ok(token):
    if not config.TURNSTILE_SECRET:
        return True
    try:
        r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',
                          data={'secret': config.TURNSTILE_SECRET, 'response': token or '', 'remoteip': _ip()},
                          timeout=10)
        return r.json().get('success') is True
    except requests.RequestException:
        return False


_CACHE_PRODUTO = {'quando': 0.0, 'produto': None}


def _produto():
    """O produto da Música (do banco, ver RepositorioMysql.produto_musica), guardado por 60 s: toda página usa."""
    import time
    if time.time() - _CACHE_PRODUTO['quando'] > 60:
        try:
            _CACHE_PRODUTO['produto'] = servicos().repositorio.produto_musica()
        except Exception as e:
            logger.error(f'[MUSICA] Erro ao buscar o produto da Música: {e}')
        _CACHE_PRODUTO['quando'] = time.time()
    return _CACHE_PRODUTO['produto']


def _pid():
    return (_produto() or {}).get('id') or 0


def _empresa():
    """Razão social, CNPJ e e-mail para os termos e a privacidade."""
    produto = _produto()
    try:
        empresa = servicos().repositorio.empresa_do_produto(produto)
    except Exception:
        empresa = {}
    cnpj = re.sub(r'\D', '', empresa.get('cnpj') or '')
    if len(cnpj) == 14:
        cnpj = f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'
    return {'razao_social': empresa.get('razao_social') or '', 'cnpj': cnpj,
            'email_suporte': (produto or {}).get('email_remetente') or empresa.get('email') or ''}


def _planos_a_venda():
    """Os planos da Música à venda (vitrine, sem renovação), do mais barato ao mais caro:
    [{slug, nome, descricao, preco, videoclipe, plano}]."""
    from database import get_plano_venda, listar_planos_produto, preco_cobrado_plano
    from musica.dominio.recursos import plano_vende_musica
    planos = []
    produto_id = _pid()
    for p in listar_planos_produto(produto_id):
        if not p['ativo'] or p.get('renovacao'):
            continue
        plano = get_plano_venda(produto_id, p['slug'])
        if not plano_vende_musica(plano):
            continue
        planos.append({'slug': plano['slug'], 'nome': plano['nome'], 'descricao': plano.get('descricao') or '',
                       'preco': preco_cobrado_plano(produto_id, plano),
                       'videoclipe': any(i.get('recurso') == VIDEOCLIPE for i in plano['principais']),
                       'plano': plano})
    return sorted(planos, key=lambda x: x['preco'])


@bp.context_processor
def _variaveis_das_paginas():
    produto = _produto()
    marca = (produto or {}).get('email_nome_remetente') or (produto or {}).get('nome') or 'Música de Presente'
    return {'marca': marca, 'turnstile_site_key': config.TURNSTILE_SITE_KEY, 'dominio_cfg': _empresa(),
            'produto_id': _pid()}


def _com_cookie_do_funil(resposta, pedido_id):
    from web.checkout import COOKIE_MAX_AGE_FUNIL
    if pedido_id:
        resposta.set_cookie(f'pedido_web_{_pid()}', str(pedido_id), max_age=COOKIE_MAX_AGE_FUNIL)
    return resposta


def _pedido_origem():
    """O pedido do cookie do funil, só se ainda é um rascunho (1003/1004) deste produto: o valor vem do navegador
    (um id inexistente quebraria a FK; o de uma compra de outra pessoa levaria o GCLID dela)."""
    cookie = request.cookies.get(f'pedido_web_{_pid()}', '')
    if not cookie.isdigit():
        return None
    from database import get_pedido_nao_finalizado
    pedido = get_pedido_nao_finalizado(int(cookie), _pid())
    return pedido['id'] if pedido else None


def _rascunho_do_funil():
    """O pedido rascunho (1004) desta visita: guarda a campanha (GCLID) desde a primeira página do anúncio."""
    from web.checkout import rastrear_visita_funil
    try:
        return rastrear_visita_funil(request, _pid(), estado_novo=1004)
    except Exception as e:
        logger.error(f'[MUSICA] Erro ao registrar a visita no funil: {e}')
        return None


# =================================================================== páginas

@bp.get('/')
def inicio():
    if not _produto():
        return _nao_encontrada()
    pedido_id = _rascunho_do_funil()
    planos = _planos_a_venda()
    preco_texto = reais(planos[0]['preco']) if planos else ''
    resposta = make_response(render_template('musica/inicio.html', ocasiao=request.args.get('ocasiao', ''),
                                             preco_texto=preco_texto))
    return _com_cookie_do_funil(resposta, pedido_id)


@bp.get('/criar')
def criar():
    if not _produto():
        return _nao_encontrada()
    pedido_id = _rascunho_do_funil()   # anúncio que leva direto ao quiz também registra a campanha
    pasta = Path(bp.static_folder) / 'estilos'
    amostras = {a.stem: url_for('musica.static', filename=f'estilos/{a.name}') for a in sorted(pasta.glob('*.mp3'))}
    resposta = make_response(render_template('musica/quiz.html', perguntas=PERGUNTAS, feminino=sorted(FEMININO),
                                             masculino=sorted(MASCULINO), amostras=amostras))
    return _com_cookie_do_funil(resposta, pedido_id)


@bp.get('/p/<token>')
def pagina_previa(token):
    """Letra, espera e prévia (o funil depois do quiz). Música já comprada vai para a página do presente."""
    musica = servicos().repositorio.por_token(token) if re.fullmatch(r'[0-9a-f]{32}', token) else None
    if not musica:
        return _nao_encontrada()
    if musica['liberada_em']:
        return redirect(url_for('musica.pagina_presente', token=token))
    return render_template('musica/pedido.html', token=token)


@bp.get('/m/<token>')
def pagina_presente(token):
    """O presente: ouvir, baixar e ver o videoclipe. Sem dados de quem comprou, sem cross-sell."""
    try:
        musica, recursos = uc.musica_liberada(servicos(), token)
    except Recusa:
        return _nao_encontrada()
    video = VIDEOCLIPE in recursos and musica['video_status'] == 'pronto'
    return render_template('musica/musica.html', musica=musica, para=regras.para_quem(musica['respostas']),
                           letra_texto=regras.para_leitura(musica['letra_exibicao']), video=video)


@bp.get('/m/<token>/<int:numero>.mp3')
def musica_completa(token, numero):
    try:
        musica, _ = uc.musica_liberada(servicos(), token)
    except Recusa:
        return _nao_encontrada()
    arquivo = servicos().arquivos.completa(token, numero)
    if numero not in (1, 2) or not arquivo.exists():
        return _nao_encontrada()
    return send_file(arquivo, mimetype='audio/mpeg', as_attachment=request.args.get('baixar') == '1',
                     download_name=f"{musica['titulo'] or 'musica'} - versao {numero}.mp3", conditional=True)


@bp.get('/m/<token>/videoclipe.mp4')
def videoclipe(token):
    try:
        musica, recursos = uc.musica_liberada(servicos(), token)
    except Recusa:
        return _nao_encontrada()
    arquivo = servicos().arquivos.videoclipe(token)
    if VIDEOCLIPE not in recursos or musica['video_status'] != 'pronto' or not arquivo.exists():
        return _nao_encontrada()
    return send_file(arquivo, mimetype='video/mp4', as_attachment=request.args.get('baixar') == '1',
                     download_name=f"{musica['titulo'] or 'videoclipe'}.mp4", conditional=True)


@bp.get('/m/<token>/videoclipe.jpg')
def capa_video(token):
    try:
        uc.musica_liberada(servicos(), token)
    except Recusa:
        return _nao_encontrada()
    arquivo = servicos().arquivos.capa_video(token)
    if not arquivo.exists():
        return _nao_encontrada()
    return send_file(arquivo, mimetype='image/jpeg')


@bp.get('/previa/<token>/<int:numero>.mp3')
def previa(token, numero):
    if not re.fullmatch(r'[0-9a-f]{32}', token) or numero not in (1, 2):
        return _nao_encontrada()
    arquivo = servicos().arquivos.previa(token, numero)
    if not arquivo.exists():
        return _nao_encontrada()
    return send_file(arquivo, mimetype='audio/mpeg')


@bp.get('/compra/<guid>')
def pagina_compra(guid):
    """Área de quem comprou: ouvir e baixar, cartão QR, presente por e-mail, fotos do videoclipe."""
    try:
        pedido, musica, recursos = uc.compra(servicos(), guid)
    except Recusa as r:
        if r.status == 409:
            return render_template('musica/legal.html', pagina='liberando', atualizado=ATUALIZADO_LEGAL), 409
        return _nao_encontrada()
    return render_template('musica/compra.html', guid=guid, musica=musica, recursos=recursos,
                           para=regras.para_quem(musica['respostas']),
                           letra_texto=regras.para_leitura(musica['letra_exibicao']),
                           link_presente=url_for('musica.pagina_presente', token=musica['token'], _external=True),
                           tem_qrcode=QRCODE in recursos, tem_presente=ENTREGA_EMAIL in recursos,
                           tem_video=VIDEOCLIPE in recursos, legenda_video=config.LEGENDA_VIDEO,
                           max_fotos=servicos().video.max_fotos)


@bp.get('/compra/<guid>/cartao')
def cartao_qrcode(guid):
    """Cartão para imprimir com o QR code que abre a página do presente (order bump)."""
    try:
        _, musica, recursos = uc.compra(servicos(), guid)
    except Recusa:
        return _nao_encontrada()
    if QRCODE not in recursos:
        return _nao_encontrada()
    link = url_for('musica.pagina_presente', token=musica['token'], _external=True)
    return render_template('musica/cartao.html', musica=musica, para=regras.para_quem(musica['respostas']),
                           qr=_qr_svg(link))


def _qr_svg(texto):
    """QR code em SVG sem tamanho fixo (escala com o cartão, não corta na impressão)."""
    import qrcode
    import qrcode.image.svg
    imagem = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, border=2,
                         error_correction=qrcode.constants.ERROR_CORRECT_M)
    svg = imagem.to_string(encoding='unicode')
    svg = re.sub(r'<\?xml[^>]*>', '', svg)
    return re.sub(r'\s(width|height)="[^"]*"', '', svg, count=2)


@bp.get('/termos')
def termos():
    return render_template('musica/legal.html', pagina='termos', atualizado=ATUALIZADO_LEGAL)


@bp.get('/privacidade')
def privacidade():
    return render_template('musica/legal.html', pagina='privacidade', atualizado=ATUALIZADO_LEGAL)


# ======================================================================= API

@bp.post('/api/musicas')
def api_criar():
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    if not _produto():
        return jsonify(erro='Este produto não está à venda agora.'), 404
    dados = request.get_json(silent=True) or {}
    if not _turnstile_ok(dados.get('turnstile')):
        return jsonify(erro='Não conseguimos confirmar que você não é um robô. Recarregue a página.'), 400
    respostas = {k: str(v).strip()[:1500] for k, v in (dados.get('respostas') or {}).items() if k in CHAVES_VALIDAS}
    whatsapp = re.sub(r'\D', '', dados.get('whatsapp') or '')[:20]
    email = (dados.get('email') or '').strip().lower()[:200]
    try:
        musica = uc.criar_musica(servicos(), _pid(), respostas, email, whatsapp, _ip(),
                                 pedido_origem_id=_pedido_origem(), dominio=_host())
    except Recusa as r:
        return _recusa(r)
    return jsonify(token=musica['token'], link=url_for('musica.pagina_previa', token=musica['token']))


@bp.get('/api/musicas/<token>')
def api_ver(token):
    musica = servicos().repositorio.por_token(token) if re.fullmatch(r'[0-9a-f]{32}', token) else None
    if not musica:
        return jsonify(erro='Não encontramos esta música.'), 404
    resposta = {
        'status': musica['status'],
        'para': regras.para_quem(musica['respostas']),
        'titulo': musica['titulo'],
        'letra': regras.para_leitura(musica['letra_exibicao']),
        'ajustes_restantes': max(0, config.LIMITE_AJUSTES_LETRA - musica['ajustes_letra']),
        'outras_versoes_restantes': max(0, config.LIMITE_OUTRA_VERSAO - musica['outras_versoes']),
    }
    if musica['liberada_em']:
        resposta['link_musica'] = url_for('musica.pagina_presente', token=token)
    elif musica['status'] == 'previa_pronta':
        from web.links import link_checkout
        resposta['previas'] = [url_for('musica.previa', token=token, numero=f['numero']) for f in musica['faixas'] or []]
        resposta['planos'] = [{'nome': p['nome'], 'descricao': p['descricao'], 'preco': reais(p['preco']),
                               'videoclipe': p['videoclipe'],
                               'link': link_checkout(_pid(), p['plano'], musica=token)}
                              for p in _planos_a_venda()]
    return jsonify(resposta)


@bp.post('/api/musicas/<token>/ajustar')
def api_ajustar(token):
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    try:
        uc.pedir_ajuste(servicos(), token, (request.get_json(silent=True) or {}).get('ajuste'))
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True)


@bp.post('/api/musicas/<token>/gerar')
def api_gerar(token):
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    try:
        uc.gerar(servicos(), token, _ip())
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True)


@bp.post('/api/musicas/<token>/outra-versao')
def api_outra_versao(token):
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    try:
        uc.outra_versao(servicos(), token)
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True)


@bp.post('/api/compra/<guid>/presente')
def api_presente(guid):
    """Entrega por e-mail para quem recebe: agora ou na data/hora escolhida (horário de Brasília)."""
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dados = request.get_json(silent=True) or {}
    quando = None
    if not dados.get('agora'):
        try:
            quando = datetime.fromisoformat(dados.get('quando') or '')
        except ValueError:
            return jsonify(erro='Escolha a data e o horário (ou "enviar agora").'), 400
        if quando.tzinfo:   # com fuso: converte para o horário de Brasília, como o resto do sistema (sem fuso)
            quando = quando.astimezone(ZoneInfo('America/Sao_Paulo')).replace(tzinfo=None)
    try:
        uc.agendar_presente(servicos(), guid, dados.get('nome'), dados.get('email'), dados.get('mensagem'), quando)
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True, agora=quando is None)


@bp.post('/api/compra/<guid>/fotos')
def api_foto(guid):
    """Uma foto do videoclipe por requisição (campo "foto"; primeira=1 recomeça a seleção)."""
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    if (request.content_length or 0) > 2 * 1024 * 1024:
        return jsonify(erro='Uma das fotos ficou grande demais. Tente outra.'), 413
    foto = request.files.get('foto')
    if not foto or not foto.filename:
        return jsonify(erro='Escolha uma foto.'), 400
    try:
        guardadas = uc.receber_foto(servicos(), guid, foto.stream, request.form.get('primeira') == '1')
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True, fotos=guardadas)


@bp.post('/api/compra/<guid>/video')
def api_video(guid):
    """Depois das fotos: começa a montar o vídeo."""
    if not _origem_confiavel():
        return jsonify(erro='Recarregue a página e tente de novo.'), 403
    dados = request.get_json(silent=True) or {}
    try:
        uc.iniciar_video(servicos(), guid, 2 if str(dados.get('versao')) == '2' else 1, dados.get('legenda') is not False)
    except Recusa as r:
        return _recusa(r)
    return jsonify(ok=True)


@bp.get('/api/compra/<guid>/video')
def api_status_video(guid):
    try:
        _, musica, _ = uc.compra(servicos(), guid)
    except Recusa as r:
        return _recusa(r)
    return jsonify(status=musica['video_status'])


@bp.post('/webhook/<provedor>')
def webhook(provedor):
    """O gerador avisa que terminou (assinatura conferida pelo adaptador). Aviso válido = 200 (quem decide é a
    consulta que ele dispara); assinatura inválida ou outro provedor = 401."""
    try:
        valido = uc.aviso_do_gerador(servicos(), provedor, request.get_data(), dict(request.headers))
    except Exception as e:
        logger.error(f'[MUSICA] Erro no webhook do gerador {provedor}: {e}')
        valido = False
    return jsonify(ok=valido), (200 if valido else 401)
