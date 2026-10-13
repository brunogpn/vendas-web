"""Rotina diária dos apps (Celery beat): avisos de vencimento e limpeza.

Avisos (regras do app original):
- entram as licenças que vencem de hoje até daqui a 7 dias;
- faltando 2 a 7 dias sai o aviso "7dias"; faltando 1 ou 0, o "1dia";
- cada aviso sai uma vez por data de vencimento (renovar gera avisos novos);
- a busca é por faixa, não por data exata: se a rotina falhar num dia, o aviso sai no seguinte;
- se o envio falhar, o registro é desfeito para tentar de novo na próxima rodada.
"""
import logging

from database import db
from apps import APPS
from apps._nucleo import auth, datas, emails
from apps._nucleo.urls import url_absoluta

logger = logging.getLogger(__name__)

DIAS_AVISO = 7


def enviar_avisos(cfg) -> dict:
    licencas = db.execute_query(
        "SELECT l.id, l.expira_em, c.email, c.nome FROM apps_licencas l "
        "JOIN apps_clientes c ON c.id = l.cliente_id "
        "WHERE l.app_slug = %s AND l.expira_em BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL %s DAY)",
        (cfg.slug, DIAS_AVISO), fetch_all=True) or []
    enviados = erros = 0
    for l in licencas:
        dias = datas.dias_entre(datas.hoje(), l['expira_em'])
        tipo = '1dia' if dias <= 1 else '7dias'
        novo = db.execute_query(
            "INSERT IGNORE INTO apps_avisos_enviados (licenca_id, tipo, expira_em) VALUES (%s, %s, %s)",
            (l['id'], tipo, l['expira_em']), return_rowcount=True)
        if not novo:
            continue
        try:
            emails.enviar_aviso_vencimento(cfg, l['email'], l['nome'], l['expira_em'], dias,
                                           url_absoluta(cfg, '/acesso'))
            enviados += 1
        except Exception as e:
            erros += 1
            logger.error(f"[APPS] Falha no aviso {tipo} da licença #{l['id']} ({cfg.slug}): {e}")
            db.execute_query(
                "DELETE FROM apps_avisos_enviados WHERE licenca_id = %s AND tipo = %s AND expira_em = %s",
                (l['id'], tipo, l['expira_em']))
    return {'app': cfg.slug, 'enviados': enviados, 'erros': erros}


def rotina_diaria() -> list[dict]:
    resultado = [enviar_avisos(cfg) for cfg in APPS.values()]
    auth.limpar_vencidos()
    logger.info(f"[APPS] Rotina diária: {resultado}")
    return resultado
