-- WhatsApp da Música (docs/MUSICA.md): 3 templates pelo número "Canção de Presente" (+55 61 8269-6770), que só
-- envia avisos — nunca entra no fluxo de venda (sem lead, sem resposta da IA).
-- Idempotente: pode rodar de novo sem duplicar nada.
SET NAMES utf8mb4;

-- 1) Número "só avisos": fora do rodízio dos links de venda, do número gravado no pedido web e da regra
--    "produto que vende pelo WhatsApp" da tela de planos; o webhook entrega tudo dele para a Música.
SET @tem = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'telefones_produto' AND COLUMN_NAME = 'responde_mensagens');
SET @sql = IF(@tem = 0,
    'ALTER TABLE telefones_produto ADD COLUMN responde_mensagens TINYINT(1) NOT NULL DEFAULT 1 COMMENT ''0 = só envia avisos (template): mensagens recebidas não viram lead nem têm resposta''',
    'SELECT 1');
PREPARE p FROM @sql; EXECUTE p; DEALLOCATE PREPARE p;

INSERT INTO telefones_produto (telefone, produto_id, api_phone_number_id, token_env_key, provedor, waba_id, responde_mensagens)
SELECT '556182696770', p.id, '1376511528883172', 'WHATSAPP_ACCESS_TOKEN_LC', 'meta', '1060756910314417', 0
FROM produtos p
WHERE p.nome = 'Música de Presente'
  AND NOT EXISTS (SELECT 1 FROM telefones_produto t WHERE t.api_phone_number_id = '1376511528883172');

-- 2) A música: o WhatsApp de quem ganha e o andamento dos envios (os wamids ligam os avisos da Meta à música).
SET @tem = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'musicas' AND COLUMN_NAME = 'presente_whatsapp');
SET @sql = IF(@tem = 0, 'ALTER TABLE musicas
    ADD COLUMN presente_whatsapp VARCHAR(20) NULL COMMENT ''WhatsApp de quem ganha (55 + DDD + número)'' AFTER presente_email,
    ADD COLUMN presente_wa_msg_id VARCHAR(128) NULL COMMENT ''wamid do presente_surpresa'' AFTER presente_falhou_em,
    ADD COLUMN presente_wa_status VARCHAR(20) NULL COMMENT ''enviado | entregue | falhou'' AFTER presente_wa_msg_id,
    ADD COLUMN presente_wa_entregue_em DATETIME NULL COMMENT ''A Meta confirmou que chegou (entrega_feita sai uma vez)'' AFTER presente_wa_status,
    ADD COLUMN presente_wa_link_em DATETIME NULL COMMENT ''Último link mandado depois do botão Ouvir minha música'' AFTER presente_wa_entregue_em,
    ADD COLUMN comprador_wa_msg_id VARCHAR(128) NULL COMMENT ''wamid do musica_pronta'' AFTER presente_wa_link_em,
    ADD COLUMN comprador_wa_em DATETIME NULL AFTER comprador_wa_msg_id,
    ADD KEY idx_musicas_presente_wa (presente_wa_msg_id),
    ADD KEY idx_musicas_comprador_wa (comprador_wa_msg_id)', 'SELECT 1');
PREPARE p FROM @sql; EXECUTE p; DEALLOCATE PREPARE p;

-- Presentes que esperavam nova tentativa do e-mail antes desta versão ficaram com o thread do envio devolvido: a
-- nova regra de "falta enviar" (thread vazio) não os pegaria nunca mais.
UPDATE musicas SET presente_thread_id = NULL
WHERE presente_enviado_em IS NULL AND presente_thread_id IS NOT NULL AND presente_falhou_em IS NULL
  AND presente_email IS NOT NULL;

-- 3) O order bump da entrega vale para e-mail e/ou WhatsApp.
UPDATE entregaveis
SET nome_venda = 'Entrega para quem vai receber (e-mail e/ou WhatsApp)',
    descricao = 'No dia e horário que você escolher, por e-mail e/ou WhatsApp, com aviso para você'
WHERE tipo = 'musica' AND recurso = 'entrega_email';

-- Conferência
SELECT telefone, produto_id, api_phone_number_id, waba_id, token_env_key, responde_mensagens
FROM telefones_produto WHERE api_phone_number_id = '1376511528883172';
