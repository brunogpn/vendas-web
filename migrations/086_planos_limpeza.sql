-- Fecha a reestruturação produto → planos → entregáveis (migration 085, docs/PLANOS.md): tira o que só
-- existia para o código antigo continuar no ar durante o deploy.
--   * views ebooks / ebooks_produto (compatibilidade da 085);
--   * apps_produto (082): virou plano com o app como item (dias no item do plano);
--   * produtos.desconto_oferta (083): virou produto_planos.desconto_oferta.
--
-- ORDEM DO DEPLOY: 085 → código novo no ar (docker compose up -d --build app worker-* beat +
-- make reload-nginx) → ESTA migration. O código antigo ainda lê tudo isto.
--
-- Backup antes (só o que some):
--   docker compose exec -T db sh -c 'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" apps_produto produtos' | gzip > backup_antes_086_$(date +%Y%m%d_%H%M%S).sql.gz

-- Itens de app gravados pelo código antigo entre a 085 e o rebuild (sem o item do plano): liga ao item
-- do plano, como a 085 fez com os anteriores — é por ele que a licença sai (dias). Idempotente; a
-- reconciliação de hora em hora (tasks.apps_reconciliar_licencas) libera os que já foram pagos.
UPDATE pedido_itens pi
JOIN pedidos p ON p.id = pi.pedido_id
JOIN plano_entregaveis pe ON pe.produto_id = p.produto_id AND pe.papel = 'principal'
JOIN produto_planos pp ON pp.id = pe.plano_id AND pp.padrao = 1
JOIN entregaveis e ON e.id = pe.entregavel_id AND e.tipo = 'app' AND e.app_slug = pi.app_slug
SET pi.ebook_produto_id = pe.id
WHERE pi.app_slug IS NOT NULL AND pi.ebook_produto_id IS NULL;

DROP VIEW IF EXISTS ebooks_produto;
DROP VIEW IF EXISTS ebooks;

DROP TABLE IF EXISTS apps_produto;

ALTER TABLE produtos DROP COLUMN desconto_oferta;
