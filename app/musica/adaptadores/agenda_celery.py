"""Agenda pelo Celery do sistema. Usa send_task pelo nome (sem importar tasks), como o fluxo do PIX.
As tarefas ficam em musica/tarefas.py; as filas, em celery_app.task_routes."""
from celery_app import celery_app


class AgendaCelery:
    def escrever_letra(self, musica_id, ajuste=None):
        celery_app.send_task('musica.escrever_letra', args=[musica_id], kwargs={'ajuste': ajuste})

    def consultar(self, musica_id, depois_de_segundos=0):
        celery_app.send_task('musica.consultar', args=[musica_id], countdown=depois_de_segundos)

    def fazer_video(self, musica_id):
        celery_app.send_task('musica.fazer_video', args=[musica_id])

    def enviar_presentes(self):
        celery_app.send_task('musica.enviar_presentes')

    def whatsapp_comprador(self, musica_id):
        celery_app.send_task('musica.whatsapp_comprador', args=[musica_id])

    def reler_status_whatsapp(self, statuses, depois_de_segundos):
        celery_app.send_task('musica.reler_status_whatsapp', args=[statuses], countdown=depois_de_segundos)
