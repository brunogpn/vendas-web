-- Limpeza do legado de entrega (antes da reestruturação produto → planos → entregáveis).
-- Nada aqui é lido pelo código desde set/2026 (levantamento em 16/10/2026):
--   * produto_bonus / produto_bump: substituídas pelo catálogo (ebooks + ebooks_produto, migration 060);
--     os pedidos antigos continuam abrindo pela cópia gravada no próprio item (nome/path_arquivo).
--   * pedido_itens.produto_bonus_id / produto_bump_id: só apontavam para essas tabelas.
--   * colunas antigas de produtos: viraram acoes_fluxo_produto (migrations 005/011) ou o catálogo;
--     só a clonagem e a tela "Dados básicos" ainda as copiavam/mostravam (removido do código).
-- Mantidas: url_arquivo_produto (PDF que a IA do WhatsApp/e-mail lê) e url_imagem_complementar (portfólio).
--
-- ORDEM DO DEPLOY: primeiro o código novo no ar (docker compose up -d --build app worker-* beat +
-- make reload-nginx) e SÓ DEPOIS esta migration — o código antigo ainda grava/lê essas colunas
-- (Dados básicos, clonar produto).
--
-- 1) Conferência (deve voltar VAZIO): produto com bônus/bump só no legado, sem vínculo no catálogo.
--   SELECT DISTINCT x.produto_id, x.origem FROM (
--     SELECT produto_id, 'bonus' origem FROM produto_bonus UNION ALL SELECT produto_id, 'bump' FROM produto_bump) x
--   WHERE NOT EXISTS (SELECT 1 FROM ebooks_produto ep WHERE ep.produto_id = x.produto_id AND ep.papel = x.origem);
--   Se voltar algo: vincular esses bônus/bumps no admin (E-books do produto) antes de seguir.
--
-- 2) Backup do que será apagado (tabelas legado + produtos inteira, por causa das colunas):
--   docker compose exec -T db sh -c 'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" produto_bonus produto_bump produtos' | gzip > backup_antes_084_$(date +%Y%m%d_%H%M%S).sql.gz

ALTER TABLE pedido_itens
    DROP FOREIGN KEY fk_pedido_itens_bonus,
    DROP FOREIGN KEY fk_pedido_itens_bump;

ALTER TABLE pedido_itens
    DROP COLUMN produto_bonus_id,
    DROP COLUMN produto_bump_id;

DROP TABLE IF EXISTS produto_bump;
DROP TABLE IF EXISTS produto_bonus;

ALTER TABLE produtos
    DROP COLUMN url_faq_produto,
    DROP COLUMN prompt_followup,
    DROP COLUMN url_audio_introducao,
    DROP COLUMN url_audio_explicativo,
    DROP COLUMN url_audio_pedido_entregue,
    DROP COLUMN imagem_checkout,
    DROP COLUMN caption_arquivo_produto,
    DROP COLUMN nome_arquivo_produto,
    DROP COLUMN mensagem_introducao,
    DROP COLUMN mensagem_pedido_enviado_sem_interesse,
    DROP COLUMN mensagem_para_pagamento,
    DROP COLUMN pix_destinatario_esperado,
    DROP COLUMN valor_minimo_pagamento,
    DROP COLUMN mensagem_pagamento_confirmado,
    DROP COLUMN mensagem_comprovante_invalido,
    DROP COLUMN url_arquivo_surpresa,
    DROP COLUMN caption_arquivo_surpresa,
    DROP COLUMN nome_arquivo_surpresa,
    DROP COLUMN url_pdf,
    DROP COLUMN url_pdf_bonus;
