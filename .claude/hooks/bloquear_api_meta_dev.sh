#!/usr/bin/env bash
# PreToolUse (Bash): no ambiente de DEV, bloqueia comandos que chamem a API oficial da Meta.
# DEV é detectado pelo marcador WHATSAPP_API_URL=http://127.0.0.1:9/ no .env — em produção o
# .env aponta pra URL real e este hook não bloqueia nada.
set -euo pipefail

cmd=$(jq -r '.tool_input.command // empty')
env_file="${CLAUDE_PROJECT_DIR:-.}/.env"

grep -qE '^WHATSAPP_API_URL=https?://127\.0\.0\.1:9/?' "$env_file" 2>/dev/null || exit 0
grep -qiE 'graph\.facebook\.com|graph\.whatsapp\.com' <<<"$cmd" || exit 0
# Só bloqueia quando há um cliente HTTP no comando — grep/leitura de código que cita o domínio passa
grep -qiE '(^|[^a-z])(curl|wget|http|httpx|requests|urllib|aiohttp)([^a-z]|$)' <<<"$cmd" || exit 0
# Exceção (pedida pelo Leo em 22/10/2026): consulta SÓ DE LEITURA dos templates e dos números de uma WABA
# (GET em /message_templates ou /phone_numbers), do /debug_token (quais WABAs um token acessa), das contas de
# WhatsApp de uma empresa (owned/client_whatsapp_business_accounts) e de um objeto pelo ID (/<id>?fields=...),
# para conferir parâmetros. Qualquer envio continua bloqueado:
# nada de POST/DELETE, corpo (-d/--data/-F) ou endpoint de mensagens.
# A checagem vale para o comando INTEIRO (não só para um trecho do curl, que o `&` da URL cortava): só o `cut -d<x>`
# que lê o token do .env é tirado antes. Qualquer -X/--request (o GET é o padrão do curl), corpo em qualquer forma
# (-d colado ou agrupado como -sd, --data*, --json, -F, --form*, -T, --upload-file), arquivo de config (-K/--config),
# --next, mais de um curl ou outro cliente HTTP (wget, python) recusa a exceção.
sem_cut=$(sed -E 's/cut +-d[^ ]*//g' <<<"$cmd")
if [ "$(grep -o 'curl' <<<"$cmd" | wc -l | tr -d ' ')" = "1" ] \
   && grep -qiE '/(message_templates|phone_numbers|debug_token|owned_whatsapp_business_accounts|client_whatsapp_business_accounts)([?"'"'"' ]|$)|/v[0-9.]+/[0-9]+\?fields=' <<<"$cmd" \
   && ! grep -qE '(^|[[:space:]"'"'"'=])-[a-zA-Z]*[dFTXK]|--(request|data|json|form|upload-file|config|next|variable|method)' <<<"$sem_cut" \
   && ! grep -qiE '/messages|/register|subscribed_apps|wget|python|requests\.|urllib|httpx|aiohttp' <<<"$cmd"; then
  exit 0
fi

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "Bloqueado pelo hook do projeto: o dev local nunca chama a API oficial da Meta (graph.facebook.com). Para testar envio, use o chip do gateway (WPP_WEB_API_URL)."
  }
}'
