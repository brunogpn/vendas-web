"""Casos de uso da Música. Só falam com as portas (s: fabrica.Servicos) — nada de Flask, SQL ou provedor aqui.

Antes de pagar:  criar_musica → escrever_letra → (pedir_ajuste)* → gerar → consultar/tratar_resultado → prévia
No checkout:     musica_para_checkout + vincular_ao_pedido (uma música por pedido; preço só do plano/bumps)
Depois de pagar: liberar_do_pedido (tasks.enviar_email_entrega) → compra (QR, presente por e-mail, videoclipe)
Rotinas:         manutencao (destravar, reconciliar), enviar_presentes, enviar_lembretes, limpar_antigas
"""
import logging
import shutil
from datetime import datetime, timedelta

from musica import config, links, mensagens
from musica.dominio import legenda, regras
from musica.dominio import modelos as m_
from musica.dominio.recursos import ENTREGA_EMAIL, MUSICA, QRCODE, VIDEOCLIPE

logger = logging.getLogger(__name__)


class Recusa(Exception):
    """Pedido da cliente que não pode ser atendido; `mensagem` vai para a tela e `status` é o HTTP."""

    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)
        self.mensagem, self.status = mensagem, status


def _agora():
    return datetime.now()   # o banco e os containers estão no horário de Brasília (TZ=America/Sao_Paulo)


def _musica(s, token):
    musica = s.repositorio.por_token(token) if token else None
    if not musica:
        raise Recusa('Não encontramos esta música.', 404)
    return musica


def _bloquear_se_comprada(musica):
    if musica['liberada_em']:
        raise Recusa('Esta música já foi comprada.')


# ============================================================== antes de pagar

def criar_musica(s, produto_id, respostas, email, whatsapp, ip, pedido_origem_id=None, dominio=None):
    if not respostas.get('nome') or not respostas.get('lembrancas') or not respostas.get('de'):
        raise Recusa('Faltou preencher o nome, as lembranças ou o seu nome.')
    if '@' not in (email or ''):
        raise Recusa('Confira o seu e-mail.')
    # Cada quiz já custa uma letra na OpenAI: limite por e-mail/IP (o de gerar() só cobre a música).
    if s.repositorio.musicas_criadas_recentes(email, ip) >= config.LIMITE_LETRAS_DIA:
        raise Recusa('Você já criou várias músicas hoje. Volte amanhã para criar outra 💛', 429)
    musica = s.repositorio.criar(produto_id, respostas, email, whatsapp, ip, pedido_origem_id, dominio)
    s.agenda.escrever_letra(musica['id'])
    return musica


def escrever_letra(s, musica_id, ajuste=None):
    """Tarefa (fila urgente: a cliente está esperando na tela)."""
    musica = s.repositorio.por_id(musica_id)
    if not musica or musica['status'] != m_.ESCREVENDO:
        return
    anterior = musica['letra_suno'] if ajuste else None
    try:
        letra = s.escritor.escrever(s.instrucoes_letra, musica['respostas'], anterior, ajuste)
    except m_.ErroLetra as erro:
        logger.error(f"[MUSICA] Letra da música #{musica_id} falhou: {erro}")
        if anterior:
            # Ajuste que falhou: a letra anterior continua valendo (não manda a cliente refazer o quiz).
            s.repositorio.atualizar(musica_id, status=m_.LETRA_PRONTA, erro=str(erro))
            s.notificador.equipe(f'Ajuste da letra da música #{musica_id} falhou: {erro}')
            return
        s.repositorio.atualizar(musica_id, status=m_.ERRO_LETRA, erro=str(erro))
        s.notificador.equipe(f'Letra da música #{musica_id} falhou: {erro}')
        return
    s.repositorio.atualizar(musica_id, status=m_.LETRA_PRONTA, titulo=letra.titulo[:255],
                            letra_exibicao=letra.letra_exibicao, letra_suno=letra.letra_suno,
                            modelo_letra=s.escritor.modelo, erro=None)


def pedir_ajuste(s, token, ajuste):
    musica = _musica(s, token)
    ajuste = (ajuste or '').strip()[:800]
    if musica['status'] != m_.LETRA_PRONTA or not ajuste:
        raise Recusa('Escreva o que você quer mudar na letra.')
    if musica['ajustes_letra'] >= config.LIMITE_AJUSTES_LETRA:
        raise Recusa('Você já usou todos os ajustes desta letra.')
    if not s.repositorio.trocar_status(musica['id'], m_.LETRA_PRONTA, m_.ESCREVENDO):   # clique duplo
        raise Recusa('A letra já está sendo reescrita.')
    s.repositorio.atualizar(musica['id'], ajustes_letra=musica['ajustes_letra'] + 1)
    s.agenda.escrever_letra(musica['id'], ajuste)


def _mandar_gerar(s, musica):
    pedido = regras.montar_geracao(musica['respostas'], musica['titulo'], musica['letra_suno'], s.estilos)
    job_id = s.gerador.criar(pedido, links.webhook(s.gerador.nome))
    s.repositorio.atualizar(musica['id'], status=m_.GERANDO, job_id=job_id, provedor=s.gerador.nome,
                            geracoes=musica['geracoes'] + 1, gerando_desde=_agora(), erro=None)
    s.agenda.consultar(musica['id'], 20)


def gerar(s, token, ip):
    """'Criar a música': cada geração custa crédito, então tem limite por e-mail/IP e trava contra clique duplo."""
    musica = _musica(s, token)
    if musica['status'] != m_.LETRA_PRONTA:
        raise Recusa('Esta música já está sendo criada.')
    if s.repositorio.geracoes_recentes(musica['email'], ip) >= config.LIMITE_PREVIAS_DIA:
        raise Recusa('Você já criou várias músicas hoje. Volte amanhã para criar outra 💛', 429)
    if not s.repositorio.trocar_status(musica['id'], m_.LETRA_PRONTA, m_.GERANDO):
        raise Recusa('Esta música já está sendo criada.')
    s.repositorio.atualizar(musica['id'], job_id=None)
    try:
        _mandar_gerar(s, musica)
    except m_.ErroGerador as erro:
        s.repositorio.atualizar(musica['id'], status=m_.LETRA_PRONTA)
        s.notificador.equipe(f"Gerador recusou a música #{musica['id']}: {erro}")
        raise Recusa('Nosso estúdio está ocupado agora. Tente de novo em alguns minutos.', 503)


def outra_versao(s, token):
    musica = _musica(s, token)
    _bloquear_se_comprada(musica)
    if musica['status'] != m_.PREVIA_PRONTA or musica['outras_versoes'] >= config.LIMITE_OUTRA_VERSAO:
        raise Recusa('Não dá para criar outra versão desta música.')
    if not s.repositorio.trocar_status(musica['id'], m_.PREVIA_PRONTA, m_.GERANDO):
        raise Recusa('A outra versão já está sendo criada.')
    s.repositorio.atualizar(musica['id'], job_id=None)   # para não ler o resultado da versão anterior
    try:
        _mandar_gerar(s, musica)
    except m_.ErroGerador as erro:
        s.repositorio.atualizar(musica['id'], status=m_.PREVIA_PRONTA, job_id=musica['job_id'])
        s.notificador.equipe(f"Gerador recusou outra versão da música #{musica['id']}: {erro}")
        raise Recusa('Nosso estúdio está ocupado agora. Tente de novo em alguns minutos.', 503)
    s.repositorio.atualizar(musica['id'], outras_versoes=musica['outras_versoes'] + 1)   # só conta se deu certo


def consultar(s, musica_id) -> bool:
    """Tarefa: pergunta ao gerador como está. Devolve True se ainda está gerando (consultar de novo)."""
    musica = s.repositorio.por_id(musica_id)
    if not musica or musica['status'] != m_.GERANDO or not musica['job_id']:
        return False
    try:
        resultado = s.gerador.consultar(musica['job_id'])
    except Exception as erro:
        # Resposta fora do formato (ou outro erro do adaptador): conta como "ainda compondo", para a trava de
        # MINUTOS_PARA_TRAVA valer — senão a música ficaria em "gerando" para sempre, sem aviso.
        logger.exception(f"[MUSICA] Consulta ao gerador da música #{musica_id} falhou: {erro}")
        resultado = m_.ResultadoGeracao(m_.GERACAO_ANDAMENTO)
    if resultado.status == m_.GERACAO_ANDAMENTO:
        if not regras.travou(musica['gerando_desde'], _agora(), config.MINUTOS_PARA_TRAVA):
            return True
        resultado = m_.ResultadoGeracao(m_.GERACAO_FALHOU, erro=f'travou (mais de {config.MINUTOS_PARA_TRAVA} min)')
    tratar_resultado(s, musica, resultado)
    atual = s.repositorio.por_id(musica_id)
    return bool(atual) and atual['status'] == m_.GERANDO and atual['job_id'] == musica['job_id']


def tratar_resultado(s, musica, resultado):
    if not s.repositorio.trocar_status(musica['id'], m_.GERANDO, m_.PROCESSANDO):
        return   # outro processo já está cuidando desta música

    if resultado.status == m_.GERACAO_FALHOU:
        logger.warning(f"[MUSICA] Gerador falhou na música #{musica['id']}: {resultado.erro}")
        if musica['geracoes'] < config.MAX_TENTATIVAS_GERACAO:
            try:
                _mandar_gerar(s, musica)
                return
            except m_.ErroGerador as erro:
                resultado = m_.ResultadoGeracao(m_.GERACAO_FALHOU, erro=str(erro))
        if musica['faixas']:
            # "Outra versão" que não saiu: a prévia anterior (arquivos intactos) continua à venda.
            s.repositorio.atualizar(musica['id'], status=m_.PREVIA_PRONTA, erro=resultado.erro)
            s.notificador.equipe(f"Outra versão da música #{musica['id']} não gerou (mantida a anterior): {resultado.erro}")
            return
        s.repositorio.atualizar(musica['id'], status=m_.ERRO, erro=resultado.erro)
        s.notificador.equipe(f"Música #{musica['id']} não gerou: {resultado.erro}")
        return

    try:
        faixas = []
        for numero, faixa in enumerate(resultado.faixas[:2], start=1):
            completa = s.arquivos.completa(musica['token'], numero)
            s.audio.baixar(faixa.url, completa)
            inicio = regras.inicio_previa(faixa.duracao, config.PREVIA_SEGUNDOS)
            s.audio.cortar_previa(completa, s.arquivos.previa(musica['token'], numero), inicio, config.PREVIA_SEGUNDOS)
            faixas.append({'numero': numero, 'duracao': faixa.duracao})
        if not faixas:
            raise RuntimeError('o gerador não devolveu nenhuma faixa')
    except Exception as erro:   # download ou corte falhou
        logger.exception(f"[MUSICA] Falha ao baixar/cortar a música #{musica['id']}")
        if regras.travou(musica['gerando_desde'], _agora(), 3 * config.MINUTOS_PARA_TRAVA):
            # Falha que persiste (ex.: link do provedor expirou): para de tentar e avisa a equipe.
            s.repositorio.atualizar(musica['id'], status=m_.ERRO, erro=str(erro)[:500])
            s.notificador.equipe(f"Música #{musica['id']} gerou, mas não deu para baixar/cortar: {erro}")
            return
        # Volta para "gerando": consultar() devolve True e a própria tarefa agenda a próxima tentativa
        # (agendar aqui também duplicaria a cadeia de consultas a cada falha).
        s.repositorio.atualizar(musica['id'], status=m_.GERANDO, erro=str(erro)[:500])
        return
    s.repositorio.atualizar(musica['id'], status=m_.PREVIA_PRONTA, faixas=faixas, erro=None)


def aviso_do_gerador(s, provedor, corpo, cabecalhos) -> bool:
    """Webhook: o gerador avisa que terminou. Só dispara a consulta (que confere tudo de novo)."""
    if provedor != s.gerador.nome:
        return False
    job_id = s.gerador.webhook_valido(corpo, cabecalhos)
    if not job_id:
        return False
    musica = s.repositorio.por_job(job_id)
    if musica and musica['status'] == m_.GERANDO:
        s.agenda.consultar(musica['id'])
    return True


# ================================================================== checkout

def musica_para_checkout(s, token, produto_id):
    """A música que este checkout vai vender: precisa ser do produto, estar com a prévia pronta e não comprada."""
    musica = s.repositorio.por_token(token) if token else None
    if not musica or musica['produto_id'] != produto_id:
        raise Recusa('Não encontramos a sua música. Volte para a página da prévia e clique em comprar de novo.')
    if musica['liberada_em']:
        raise Recusa('Esta música já foi comprada. Veja o seu e-mail.')
    if musica['status'] != m_.PREVIA_PRONTA:
        raise Recusa('A sua música ainda não ficou pronta. Volte para a página da prévia.')
    return musica


def vincular_ao_pedido(s, token, pedido_id, produto_id):
    musica = musica_para_checkout(s, token, produto_id)
    s.repositorio.vincular_pedido(musica['id'], pedido_id)
    return musica


# ============================================================ depois de pagar

def liberar_do_pedido(s, pedido_id) -> bool:
    """Ponto único (tasks.enviar_email_entrega + reconciliação): pedido pago com item de música libera a música.
    Idempotente. Devolve True se liberou agora."""
    recursos = s.repositorio.recursos_do_pedido(pedido_id)
    musica = s.repositorio.do_pedido(pedido_id)
    if MUSICA not in recursos and not musica:
        return False   # pedido de e-book
    pedido = s.repositorio.pedido_pago(pedido_id)
    if not pedido:
        return False
    if not musica:
        s.notificador.equipe(f'Pedido #{pedido_id} pago com música, mas sem música ligada a ele')
        return False
    if not s.repositorio.marcar_liberada(musica['id'], pedido_id):
        if musica['liberada_em'] and musica['pedido_id'] != pedido_id:
            s.notificador.equipe(f"Música #{musica['id']} paga de novo pelo pedido #{pedido_id} "
                                 f"(já liberada pelo #{musica['pedido_id']}): avaliar devolução")
        return False
    logger.info(f"[MUSICA] Música #{musica['id']} liberada pelo pedido #{pedido_id} ({sorted(recursos)})")
    if MUSICA not in recursos:
        # O checkout gravou a música do pedido (musica_pedidos), mas não os itens (falha no criar_itens_pedido_web):
        # a música sai mesmo assim; videoclipe/QR/presente dependem dos itens — o atendimento confere.
        s.notificador.equipe(f"Pedido #{pedido_id} pago sem os itens gravados: música #{musica['id']} liberada, "
                             "mas conferir videoclipe/QR/entrega comprados")
    if musica['whatsapp']:
        s.notificador.whatsapp(musica['whatsapp'], 'musica_pronta',
                               [musica['respostas'].get('de'), regras.para_quem(musica['respostas']),
                                links.compra(pedido['guid'], pedido.get('dns_origem') or musica['dominio'])])
    return True


def compra(s, guid):
    """(pedido, música, recursos) da área de quem comprou; Recusa se o pedido não está pago ou não tem música."""
    pedido = s.repositorio.pedido_por_guid(guid) if guid else None
    if not pedido or pedido['estado_id'] != 1000:
        raise Recusa('Não encontramos esta compra.', 404)
    musica = s.repositorio.do_pedido(pedido['id'])
    if not musica:
        raise Recusa('Não encontramos esta compra.', 404)
    if not musica['liberada_em']:
        liberar_do_pedido(s, pedido['id'])   # rede de segurança: pagou e a liberação ainda não rodou
        musica = s.repositorio.do_pedido(pedido['id'])
        if not musica['liberada_em']:
            raise Recusa('A sua música está sendo liberada. Tente de novo em alguns minutos.', 409)
    return pedido, musica, s.repositorio.recursos_do_pedido(pedido['id'])


def musica_liberada(s, token):
    """A música da página do presente (/musica/m/<token>) e o que o pedido comprou."""
    musica = s.repositorio.por_token(token) if token else None
    if not musica or not musica['liberada_em'] or not musica['pedido_id']:
        raise Recusa('Não encontramos esta música.', 404)
    return musica, s.repositorio.recursos_do_pedido(musica['pedido_id'])


def pode_qrcode(recursos):
    return QRCODE in recursos


def agendar_presente(s, guid, nome, email, mensagem, quando):
    """Entrega por e-mail para quem recebe (order bump). `quando` None = enviar agora."""
    _, musica, recursos = compra(s, guid)
    if ENTREGA_EMAIL not in recursos:
        raise Recusa('A entrega por e-mail não faz parte desta compra.', 403)
    if musica['presente_enviado_em'] and not musica['presente_falhou_em']:
        raise Recusa('Esta música já foi enviada.')   # depois de desistir, ela pode corrigir o e-mail e tentar de novo
    nome, email = (nome or '').strip()[:120], (email or '').strip()[:200]
    erro = regras.validar_presente(nome, email, quando, _agora())
    if erro:
        raise Recusa(erro)
    s.repositorio.atualizar(musica['id'], presente_nome=nome, presente_email=email,
                            presente_mensagem=(mensagem or '').strip()[:500] or None, presente_em=quando,
                            presente_enviado_em=None, presente_tentativas=0, presente_thread_id=None,
                            presente_falhou_em=None)
    if not quando:
        s.agenda.enviar_presentes()


def _email_de_quem_comprou(s, musica):
    pedido = s.repositorio.pedido_pago(musica['pedido_id']) if musica['pedido_id'] else None
    return (pedido or {}).get('email') or musica['email']


def enviar_presentes(s) -> int:
    """Tarefa (beat a cada 5 min e logo após 'enviar agora'): e-mails de presente cujo horário chegou.
    Sempre com cópia (cc) para quem comprou. Erro no envio entra na mesma regra da devolução (_nao_chegou)."""
    enviados = 0
    for musica in s.repositorio.presentes_para_enviar():
        if not s.repositorio.marcar_presente_enviado(musica['id']):
            continue   # outra execução pegou este
        tentativa = (musica['presente_tentativas'] or 0) + 1
        assunto, corpo = mensagens.presente(musica['presente_nome'], musica['respostas'].get('de') or 'Alguém especial',
                                            musica['titulo'] or 'sua música', musica['presente_mensagem'],
                                            links.presente(musica))
        try:
            thread_id = s.notificador.email(musica['produto_id'], musica['presente_email'], assunto, corpo,
                                            cc=_email_de_quem_comprou(s, musica))
        except Exception as erro:
            logger.exception(f"[MUSICA] Falha ao enviar o presente da música #{musica['id']} (envio {tentativa})")
            s.repositorio.atualizar(musica['id'], presente_tentativas=tentativa)
            _nao_chegou(s, s.repositorio.por_id(musica['id']), f'erro no envio: {erro}')
            continue
        s.repositorio.atualizar(musica['id'], presente_tentativas=tentativa, presente_thread_id=thread_id)
        enviados += 1
    return enviados


def presente_devolvido(s, thread_id, recusados) -> bool:
    """A leitura da caixa do admin@ (fluxo_email_conversas) achou uma devolução (mailer-daemon). Se for de um
    presente da Música, agenda a próxima tentativa. `recusados` = endereços que a devolução diz que recusaram
    (vazio: ela não disse). True se a devolução era nossa."""
    recusados = {e.strip().lower() for e in recusados or ()}
    musica = s.repositorio.presente_por_devolucao(thread_id, sorted(recusados))
    if not musica or not musica['presente_enviado_em']:
        return False
    if recusados and musica['presente_email'].lower() not in recusados:
        # Quem recusou não foi quem recebe: foi a cópia de quem comprou que voltou (ela vai no mesmo thread).
        # O presente em si chegou — nada a reenviar.
        logger.info(f"[MUSICA] Devolução no thread do presente #{musica['id']} é da cópia de quem comprou; ignorada")
        return True
    _nao_chegou(s, musica, 'devolvido pelo servidor de quem recebe (caixa lotada ou endereço com problema)')
    return True


def _nao_chegou(s, musica, motivo):
    """Até PRESENTE_MAX_TENTATIVAS envios, com as esperas de PRESENTE_ESPERAS_HORAS; depois, avisa quem comprou."""
    feitas = musica['presente_tentativas'] or 0
    if feitas < config.PRESENTE_MAX_TENTATIVAS:
        espera = config.PRESENTE_ESPERAS_HORAS[min(max(feitas, 1), len(config.PRESENTE_ESPERAS_HORAS)) - 1]
        s.repositorio.atualizar(musica['id'], presente_enviado_em=None, presente_em=_agora() + timedelta(hours=espera))
        logger.warning(f"[MUSICA] Presente da música #{musica['id']} não chegou ({motivo}); "
                       f"envio {feitas + 1} de {config.PRESENTE_MAX_TENTATIVAS} em {espera} h")
        return
    s.repositorio.atualizar(musica['id'], presente_falhou_em=_agora())
    assunto, corpo = mensagens.presente_nao_entregue(musica['presente_nome'], musica['presente_email'],
                                                     links.presente(musica), feitas)
    try:
        s.notificador.email(musica['produto_id'], _email_de_quem_comprou(s, musica), assunto, corpo)
    except Exception:
        logger.exception(f"[MUSICA] Falha ao avisar quem comprou a música #{musica['id']}")
    s.notificador.equipe(f"Presente da música #{musica['id']} não chegou para {musica['presente_email']} depois de "
                         f"{feitas} envios ({motivo}); quem comprou foi avisado")


def _compra_com_video(s, guid):
    _, musica, recursos = compra(s, guid)
    if VIDEOCLIPE not in recursos:
        raise Recusa('O videoclipe não faz parte desta compra.', 403)
    if musica['video_status'] == 'fazendo':
        raise Recusa('O vídeo já está sendo feito.')
    return musica


def receber_foto(s, guid, arquivo, primeira):
    """Videoclipe (plano com vídeo): UMA foto por requisição (cada uma fica bem abaixo do limite de 1 MB do nginx;
    o navegador reduz antes de enviar). `primeira` recomeça a seleção. Devolve quantas fotos já estão guardadas."""
    musica = _compra_com_video(s, guid)
    pasta = s.arquivos.pasta_video(musica['token']) / 'fotos'
    if primeira:
        shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True, exist_ok=True)
    guardadas = len(list(pasta.glob('*.jpg')))
    if guardadas >= s.video.max_fotos:
        raise Recusa(f'Escolha até {s.video.max_fotos} fotos.')
    try:
        s.video.preparar_foto(arquivo, pasta / f'{guardadas:02d}.jpg')
    except Exception:
        logger.warning(f"[MUSICA] Foto {guardadas} da música #{musica['id']} não abriu")
        raise Recusa('Não conseguimos abrir uma das fotos. Use fotos em JPG ou PNG.')
    return guardadas + 1


def iniciar_video(s, guid, versao, com_legenda):
    """Depois das fotos: agenda a montagem (fila baixa: ocupa o processador ~2 min)."""
    musica = _compra_com_video(s, guid)
    if not list((s.arquivos.pasta_video(musica['token']) / 'fotos').glob('*.jpg')):
        raise Recusa('Escolha pelo menos uma foto.')
    s.repositorio.atualizar(musica['id'], video_status='fazendo', video_versao=2 if versao == 2 else 1,
                            video_legenda=1 if com_legenda else 0, video_erro=None)
    s.agenda.fazer_video(musica['id'])


def fazer_video(s, musica_id):
    """Tarefa (fila baixa)."""
    musica = s.repositorio.por_id(musica_id)
    if not musica or musica['video_status'] != 'fazendo':
        return
    token = musica['token']
    pasta = s.arquivos.pasta_video(token)
    fotos = sorted((pasta / 'fotos').glob('*.jpg'))
    mp3 = s.arquivos.completa(token, musica['video_versao'] or 1)
    arquivo_legenda = None
    if musica['video_legenda'] and s.transcritor:
        try:   # se a legenda falhar, o vídeo sai sem ela
            linhas = legenda.linhas_da_letra(musica['letra_suno'])
            tempos = legenda.alinhar(linhas, s.transcritor.palavras(mp3, ' '.join(linhas)))
            if tempos:
                arquivo_legenda = pasta / 'letra.ass'
                legenda.gerar_ass(tempos, arquivo_legenda)
        except Exception:
            logger.exception(f'[MUSICA] Legenda do videoclipe #{musica_id} falhou; seguindo sem legenda')
    respostas = musica['respostas']
    try:
        s.video.montar(fotos, mp3, s.arquivos.videoclipe(token), musica['titulo'] or 'Música de presente',
                       regras.para_quem(respostas), respostas.get('de') or '', legenda_ass=arquivo_legenda)
    except Exception as erro:
        logger.exception(f'[MUSICA] Videoclipe #{musica_id} falhou')
        s.repositorio.atualizar(musica_id, video_status='erro', video_erro=str(erro)[:500])
        s.notificador.equipe(f'Videoclipe da música #{musica_id} falhou: {erro}')
        return
    s.repositorio.atualizar(musica_id, video_status='pronto', video_erro=None)


# =================================================================== rotinas

def manutencao(s) -> dict:
    """Beat a cada 5 min: destrava o que uma tarefa perdida (worker reiniciado) deixou parado e reconcilia pagos."""
    letras = 0
    for musica_id in s.repositorio.paradas(m_.ESCREVENDO, 10):
        musica = s.repositorio.por_id(musica_id)
        if musica and musica['letra_suno']:
            # Era um ajuste: volta para a letra que ela já tinha (e devolve o ajuste que não saiu).
            s.repositorio.atualizar(musica_id, status=m_.LETRA_PRONTA, erro='ajuste parado (tarefa perdida)',
                                    ajustes_letra=max(0, musica['ajustes_letra'] - 1))
        else:
            s.repositorio.atualizar(musica_id, status=m_.ERRO_LETRA, erro='letra parada (tarefa perdida)')
        letras += 1
    videos = 0
    for musica in s.repositorio.videos_parados(20):
        # Montagem perdida (worker reiniciado no meio): as fotos continuam no disco — retoma uma vez; se parar de
        # novo, libera para ela tentar outra vez e avisa a equipe.
        if musica['video_erro'] != 'retomado':
            s.repositorio.atualizar(musica['id'], video_erro='retomado')
            s.agenda.fazer_video(musica['id'])
        else:
            s.repositorio.atualizar(musica['id'], video_status='erro', video_erro='a montagem parou duas vezes')
            s.notificador.equipe(f"Videoclipe da música #{musica['id']} parou duas vezes")
        videos += 1
    consultas = 0
    # Só música parada além do tempo de trava: antes disso a própria cadeia de consultas resolve (e uma segunda
    # cadeia em paralelo dobraria as chamadas ao gerador).
    for musica_id in s.repositorio.paradas(m_.GERANDO, config.MINUTOS_PARA_TRAVA + 2):
        s.agenda.consultar(musica_id)
        consultas += 1
    for musica in s.repositorio.presentes_sem_confirmacao(30):
        # Marcado como enviado, mas o envio não terminou (worker caiu entre a marcação e o Gmail): manda de novo.
        logger.warning(f"[MUSICA] Presente da música #{musica['id']} ficou sem confirmação de envio; reenviando")
        s.repositorio.atualizar(musica['id'], presente_enviado_em=None)
    liberadas = sum(1 for pedido_id in s.repositorio.pagas_sem_liberar() if liberar_do_pedido(s, pedido_id))
    if liberadas:
        s.notificador.equipe(f'{liberadas} música(s) paga(s) só foram liberadas pela reconciliação')
    return {'letras_destravadas': letras, 'videos_destravados': videos, 'consultas': consultas, 'liberadas': liberadas,
            'presentes': enviar_presentes(s)}


def enviar_lembretes(s) -> int:
    """Quem ouviu a prévia e não comprou: e-mail 1 h e 24 h depois (WhatsApp quando houver número)."""
    enviados = 0
    for numero in (1, 2):
        for musica in s.repositorio.para_lembrete(numero):
            s.repositorio.atualizar(musica['id'], **{f'lembrete{numero}_em': _agora()})
            respostas = musica['respostas']
            assunto, corpo = mensagens.lembrete(numero, respostas.get('de') or '', regras.para_quem(respostas),
                                                links.previa(musica))
            try:
                s.notificador.email(musica['produto_id'], musica['email'], assunto, corpo)
                enviados += 1
            except Exception:
                logger.exception(f"[MUSICA] Lembrete {numero} da música #{musica['id']} falhou")
    return enviados


def limpar_antigas(s) -> int:
    """Músicas não compradas há mais de 90 dias: apaga do banco e do disco (promessa da política de privacidade)."""
    apagadas = 0
    for musica in s.repositorio.nao_pagas_antigas(config.DIAS_GUARDAR_NAO_PAGAS):
        s.arquivos.apagar(musica['token'])
        s.repositorio.apagar(musica['id'])
        apagadas += 1
    return apagadas
