"""Tarefas Celery da Música (finas: só chamam os casos de uso). Filas em celery_app.task_routes:
letra na urgente (a cliente está esperando na tela), geração/consulta/e-mails na normal, videoclipe na baixa
(ocupa o processador ~2 min; a concorrência 2 da fila baixa segura o pico das datas fortes)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

INTERVALO_CONSULTA = 10   # segundos entre as consultas ao gerador enquanto compõe


def _s():
    from musica.fabrica import servicos
    return servicos()


@shared_task(name='musica.escrever_letra')
def escrever_letra(musica_id, ajuste=None):
    from musica import casos_de_uso
    casos_de_uso.escrever_letra(_s(), musica_id, ajuste)


@shared_task(name='musica.consultar')
def consultar(musica_id):
    from musica import casos_de_uso
    s = _s()
    if casos_de_uso.consultar(s, musica_id):
        s.agenda.consultar(musica_id, INTERVALO_CONSULTA)


@shared_task(name='musica.fazer_video')
def fazer_video(musica_id):
    from musica import casos_de_uso
    casos_de_uso.fazer_video(_s(), musica_id)


@shared_task(name='musica.enviar_presentes')
def enviar_presentes():
    from musica import casos_de_uso
    return casos_de_uso.enviar_presentes(_s())


@shared_task(name='musica.manutencao')
def manutencao():
    from musica import casos_de_uso
    resultado = casos_de_uso.manutencao(_s())
    if any(resultado.values()):
        logger.info(f'[MUSICA] Manutenção: {resultado}')
    return resultado


@shared_task(name='musica.lembretes')
def lembretes():
    from musica import casos_de_uso
    return casos_de_uso.enviar_lembretes(_s())


@shared_task(name='musica.limpeza')
def limpeza():
    from musica import casos_de_uso
    return casos_de_uso.limpar_antigas(_s())


@shared_task(name='musica.whatsapp_comprador', bind=True, max_retries=3)
def whatsapp_comprador(self, musica_id):
    """Template musica_pronta para quem comprou. Erro passageiro da Meta: tenta de novo em 1, 2 e 4 min."""
    from musica import casos_de_uso
    from whatsapp import ErroTransienteWhatsApp
    try:
        casos_de_uso.whatsapp_comprador(_s(), musica_id)
    except ErroTransienteWhatsApp as exc:
        raise self.retry(exc=exc, countdown=60 * 2 ** self.request.retries)
    except Exception:
        logger.exception(f'[MUSICA] musica_pronta da música #{musica_id} não saiu')



@shared_task(name='musica.reler_status_whatsapp')
def reler_status_whatsapp(statuses):
    """Segunda leitura dos avisos da Meta que chegaram antes de o wamid do presente ser gravado."""
    from musica import casos_de_uso
    casos_de_uso.webhook_whatsapp(_s(), {'statuses': statuses}, ultima_tentativa=True)
