-- O Plano Guiado do Fatia (produto 16, criado em 14/10/2026 como "produto do tipo app") vira o plano
-- "completo" do próprio Fatia (produto 12) — ver docs/PLANOS.md. Depois desta migration o produto 16 deixa
-- de existir: pedidos, licenças, PIX e o resto do histórico passam para o 12 (plano Completo), a configuração
-- copiada na criação do 16 (fluxos do WhatsApp, mensagens, chave PIX, cartão, planilhas do Ads) é apagada e
-- os links antigos /pay/16 e /pay2/16 passam a redirecionar para o Completo do 12 (produtos_redirecionados).
-- Para a cliente nada muda: Estante, app e licença continuam iguais; a renovação passa a ser a do 12.
--
-- ORDEM DO DEPLOY: 085 → código novo → 084 e 086 → ESTA. Precisa da 085 (planos) e do código novo.
-- Tudo numa transação: se qualquer comando falhar, nada é aplicado (o cliente mysql para no erro e a
-- transação aberta é desfeita ao desconectar).
--
-- Backup antes (o que muda ou é apagado):
--   docker compose exec -T db sh -c 'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" pedidos pedido_itens apps_licenca_pedidos pagamento_pix devolucoes_pix notificacoes_pedido emails_atendimento campanhas orcamento_campanha whatsapp_custo_diario produto_planos plano_entregaveis acoes_fluxo_produto mensagens_sugeridas_produto chaves_pix_produto config_cartao_produto google_ads_planilha_dns usuario_produtos produtos' | gzip > backup_antes_087_$(date +%Y%m%d_%H%M%S).sql.gz
--
-- Conferência ANTES — o 12 precisa ter planilha do Google Ads para cada domínio por onde o 16 vendeu (as do
-- 16 são apagadas; pedido pago com GCLID ainda não enviado vai pela planilha do 12). Deve voltar VAZIO:
--   SELECT DISTINCT p.dns_origem FROM pedidos p WHERE p.produto_id = 16 AND p.dns_origem <> ''
--     AND NOT EXISTS (SELECT 1 FROM google_ads_planilha_dns g WHERE g.produto_id = 12 AND g.dns = p.dns_origem AND g.ativo = 1);
--
-- Conferência DEPOIS (tudo 0, e redirecionamento = 1):
--   SELECT (SELECT COUNT(*) FROM produtos WHERE id = 16) produto,
--          (SELECT COUNT(*) FROM pedidos WHERE produto_id = 16) pedidos,
--          (SELECT COUNT(*) FROM pedido_itens pi JOIN plano_entregaveis pe ON pe.id = pi.ebook_produto_id
--            WHERE pe.produto_id = 16) itens,
--          (SELECT COUNT(*) FROM produtos_redirecionados WHERE produto_id = 16) redirecionamento;

-- Links de checkout de produtos que deixaram de existir (viraram plano de outro produto): /pay/<antigo>
-- redireciona para o plano, mantendo ?pedido=, ?ref= e ?oferta=. Sem FK no id antigo (o produto some).
CREATE TABLE IF NOT EXISTS produtos_redirecionados (
    produto_id          INT       NOT NULL PRIMARY KEY COMMENT 'Id do produto que deixou de existir',
    produto_destino_id  INT       NOT NULL,
    plano_id            INT       NOT NULL,
    criado_em           TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_produtos_redirecionados_destino FOREIGN KEY (produto_destino_id) REFERENCES produtos (id),
    CONSTRAINT fk_produtos_redirecionados_plano FOREIGN KEY (plano_id) REFERENCES produto_planos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

START TRANSACTION;

SET @origem = 16, @destino = 12;
SET @plano_origem = (SELECT id FROM produto_planos WHERE produto_id = @origem AND padrao = 1);
SET @basico = (SELECT id FROM produto_planos WHERE produto_id = @destino AND padrao = 1);

-- ---------------------------------------------------------------- 1. plano Completo no 12
-- Criado com o nome, a descrição, as imagens, o preço e o desconto de oferta do Guiado, se ainda não existir
-- (o nome pode ser trocado depois no admin). Itens: o App Fatias (mesmos dias), os do Básico e os de QUALQUER
-- plano do 16 que ainda faltarem — todo item já vendido no 16 tem onde se apoiar.
INSERT INTO produto_planos (produto_id, slug, nome, descricao, imagem_grande, imagem_pequena, preco_original,
                            preco_promocional, desconto_oferta, padrao, vitrine, renovacao, ordem, ativo)
SELECT @destino, 'completo', o.nome, o.descricao, o.imagem_grande, o.imagem_pequena, o.preco_original,
       o.preco_promocional, o.desconto_oferta, 0, 1, 0, 2, 1
FROM produto_planos o
WHERE o.id = @plano_origem AND @basico IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM produto_planos WHERE produto_id = @destino AND slug = 'completo');
SET @completo = (SELECT id FROM produto_planos WHERE produto_id = @destino AND slug = 'completo');

-- O app vem primeiro (ordem 1): o preço do plano fica no primeiro item principal do pedido.
INSERT INTO plano_entregaveis (produto_id, plano_id, entregavel_id, papel, preco_original, preco_promocional, ordem, dias)
SELECT @destino, @completo, pe.entregavel_id, 'principal', 0, 0, 1, MAX(pe.dias)
FROM plano_entregaveis pe JOIN entregaveis e ON e.id = pe.entregavel_id AND e.tipo = 'app'
WHERE pe.produto_id = @origem AND pe.papel = 'principal' AND @completo IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM plano_entregaveis d WHERE d.plano_id = @completo AND d.entregavel_id = pe.entregavel_id)
GROUP BY pe.entregavel_id;

INSERT INTO plano_entregaveis (produto_id, plano_id, entregavel_id, papel, preco_original, preco_promocional, ordem, dias)
SELECT @destino, @completo, b.entregavel_id, b.papel, b.preco_original, b.preco_promocional,
       IF(b.papel = 'principal', b.ordem + 1, b.ordem), b.dias
FROM plano_entregaveis b
WHERE b.plano_id = @basico AND @completo IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM plano_entregaveis d WHERE d.plano_id = @completo AND d.entregavel_id = b.entregavel_id);

INSERT INTO plano_entregaveis (produto_id, plano_id, entregavel_id, papel, preco_original, preco_promocional, ordem, dias)
SELECT @destino, @completo, o.entregavel_id, MIN(o.papel), MAX(o.preco_original), MAX(o.preco_promocional),
       MIN(o.ordem) + 10, MAX(o.dias)
FROM plano_entregaveis o
WHERE o.produto_id = @origem AND @completo IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM plano_entregaveis d WHERE d.plano_id = @completo AND d.entregavel_id = o.entregavel_id)
GROUP BY o.entregavel_id;

-- ---------------------------------------------------------------- 2. histórico do 16 → 12 (Completo)
-- As colunas "ON UPDATE CURRENT_TIMESTAMP" são preservadas: a reconciliação de PIX, a varredura do cartão e
-- os follow-ups usam data_ultima_atualizacao como relógio — mover o pedido não pode reiniciar esse relógio.
UPDATE pedido_itens pi
JOIN plano_entregaveis o ON o.id = pi.ebook_produto_id AND o.produto_id = @origem
JOIN plano_entregaveis d ON d.plano_id = @completo AND d.entregavel_id = o.entregavel_id
SET pi.ebook_produto_id = d.id;

UPDATE pedidos SET produto_id = @destino, plano_id = @completo, data_ultima_atualizacao = data_ultima_atualizacao
WHERE produto_id = @origem AND @completo IS NOT NULL;

UPDATE apps_licenca_pedidos  SET produto_id = @destino WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE pagamento_pix         SET produto_id = @destino WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE campanhas             SET produto_id = @destino WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE devolucoes_pix        SET produto_id = @destino, atualizado_em = atualizado_em
WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE notificacoes_pedido   SET produto_id = @destino, updated_at = updated_at
WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE emails_atendimento    SET produto_id = @destino, updated_at = updated_at
WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE orcamento_campanha    SET produto_id = @destino, updated_at = updated_at
WHERE produto_id = @origem AND @completo IS NOT NULL;
UPDATE whatsapp_custo_diario SET produto_id = @destino, atualizado_em = atualizado_em
WHERE produto_id = @origem AND @completo IS NOT NULL;

INSERT INTO produtos_redirecionados (produto_id, produto_destino_id, plano_id)
SELECT @origem, @destino, @completo FROM DUAL
WHERE @completo IS NOT NULL AND EXISTS (SELECT 1 FROM produtos WHERE id = @origem)
ON DUPLICATE KEY UPDATE produto_destino_id = VALUES(produto_destino_id), plano_id = VALUES(plano_id);

-- ---------------------------------------------------------------- 3. configuração do 16 (cópia do 12)
DELETE FROM acoes_fluxo_produto         WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM mensagens_sugeridas_produto WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM variantes_fluxo_cursor      WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM notificacoes_telefone       WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM telefones_produto           WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM usuario_produtos            WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM chaves_pix_produto          WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM config_cartao_produto       WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM google_ads_planilha_dns     WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM plano_entregaveis           WHERE produto_id = @origem AND @completo IS NOT NULL;
DELETE FROM produto_planos              WHERE produto_id = @origem AND @completo IS NOT NULL;
-- Se algo ainda apontar para o 16 (FK), este DELETE falha e a transação inteira é desfeita.
DELETE FROM produtos                    WHERE id = @origem AND @completo IS NOT NULL;

COMMIT;
