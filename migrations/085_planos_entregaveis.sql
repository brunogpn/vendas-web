-- Reestruturação: produto (campanha, ISBN, NF-e) → planos (ofertas: Básico, Completo, Renovação...)
-- → entregáveis (e-book ou app). Ver docs/PLANOS.md.
--
-- * produto_planos (nova): cada oferta do produto, com nome, descrição, imagens, preço e desconto
--   de oferta próprios. 1 plano padrão por produto (o do WhatsApp e do link sem ?plano=).
-- * ebooks → entregaveis (IDs preservados) + tipo ('ebook' | 'app') + app_slug; app não tem arquivo.
-- * ebooks_produto → plano_entregaveis (IDs preservados: pedido_itens.ebook_produto_id continua
--   apontando para o vínculo certo) + plano_id + dias (dias de acesso, quando o item é app).
--   Um plano pode ter vários principais (Completo = e-book + app); o preço do vínculo só vale
--   para order bump — o preço da oferta é o do plano.
-- * pedidos.plano_id: qual oferta foi comprada (NULL = pedidos anteriores).
--
-- Dados: cada produto com e-book principal ganha o plano padrão "basico" com nome/descrição/capas/
-- preço do principal e o desconto de oferta do produto; produtos de app (apps_produto) ganham o
-- plano padrão com os dados do app e o entregável "App ..." como principal. Nada muda para a cliente.
--
-- ORDEM DO DEPLOY: rodar ANTES de subir o código novo. As views `ebooks`/`ebooks_produto` (com os
-- nomes antigos) mantêm o código antigo funcionando até o rebuild; a 086 as remove depois.
-- Não usar o admin de e-books/planos entre esta migration e o rebuild (o código antigo grava nas views).
--
-- CONFERÊNCIA depois de rodar (antes do rebuild) — produtos ativos SEM plano padrão à venda. Com o código
-- novo, os pedidos do WhatsApp deles nascem sem itens (Estante vazia) e o admin recebe alerta. Hoje eles já
-- estão assim (sem e-book principal); se algum vende de verdade, cadastrar o plano no admin depois do deploy:
--   SELECT p.id, p.nome FROM produtos p WHERE p.ativo = 1 AND NOT EXISTS (
--     SELECT 1 FROM produto_planos pp JOIN plano_entregaveis pe ON pe.plano_id = pp.id AND pe.papel = 'principal'
--     WHERE pp.produto_id = p.id AND pp.padrao = 1 AND pp.ativo = 1);

CREATE TABLE IF NOT EXISTS produto_planos (
    id                INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    produto_id        INT           NOT NULL,
    slug              VARCHAR(30)   NOT NULL COMMENT 'Identifica o plano na URL: /pay/<produto>?plano=<slug>',
    nome              VARCHAR(255)  NOT NULL COMMENT 'Nome da oferta no checkout (ex.: Fatia de Bolo — Completo)',
    descricao         TEXT          NULL,
    imagem_grande     VARCHAR(255)  NULL COMMENT 'Arquivo em static/images/',
    imagem_pequena    VARCHAR(255)  NULL,
    preco_original    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    preco_promocional DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Valor cobrado pelo plano (sem os bumps)',
    desconto_oferta   DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Desconto do popup/Estante (token assinado); 0 = sem oferta',
    padrao            TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '1 = plano do WhatsApp e do link sem ?plano=',
    vitrine           TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '1 = pode aparecer na landing e no cross-sell',
    renovacao         TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '1 = renovação do app (aparece em "Meu acesso", não na vitrine)',
    ordem             TINYINT UNSIGNED NOT NULL DEFAULT 1,
    ativo             TINYINT(1)    NOT NULL DEFAULT 1,
    padrao_produto    INT GENERATED ALWAYS AS (CASE WHEN padrao = 1 THEN produto_id END) VIRTUAL,
    criado_em         TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_produto_planos_slug (produto_id, slug),
    UNIQUE KEY uk_produto_planos_padrao (padrao_produto),
    CONSTRAINT fk_produto_planos_produto FOREIGN KEY (produto_id) REFERENCES produtos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------- catálogo
RENAME TABLE ebooks TO entregaveis, ebooks_produto TO plano_entregaveis;

ALTER TABLE entregaveis
    ADD COLUMN tipo ENUM('ebook','app') NOT NULL DEFAULT 'ebook' AFTER id,
    ADD COLUMN app_slug VARCHAR(40) NULL COMMENT 'Quando tipo=app: pasta app/apps/<slug>' AFTER tipo,
    MODIFY descricao VARCHAR(500) NULL,
    MODIFY path_arquivo VARCHAR(255) NULL COMMENT 'Arquivo do e-book (NULL para app)',
    MODIFY nome_arquivo VARCHAR(255) NULL;

-- A FK de ebook_id sai antes: o MySQL não renomeia coluna de FK numa alteração que copia a tabela.
ALTER TABLE plano_entregaveis DROP FOREIGN KEY fk_ebooks_produto_ebook;

ALTER TABLE plano_entregaveis
    DROP INDEX uk_ebooks_produto_principal,
    DROP COLUMN produto_principal,
    RENAME COLUMN ebook_id TO entregavel_id,
    RENAME INDEX idx_ebooks_produto_ebook TO idx_plano_entregaveis_entregavel,
    RENAME INDEX idx_ebooks_produto_produto TO idx_plano_entregaveis_produto,
    ADD COLUMN plano_id INT NULL AFTER produto_id,
    ADD COLUMN dias INT NULL COMMENT 'Dias de acesso quando o entregável é app' AFTER ordem,
    ADD KEY idx_plano_entregaveis_plano (plano_id, papel, ordem),
    ADD CONSTRAINT fk_plano_entregaveis_entregavel FOREIGN KEY (entregavel_id) REFERENCES entregaveis (id),
    ADD CONSTRAINT fk_plano_entregaveis_plano FOREIGN KEY (plano_id) REFERENCES produto_planos (id);

-- ---------------------------------------------------------------- dados: plano padrão por produto
-- Produtos de e-book: o principal de hoje vira o plano "basico".
INSERT INTO produto_planos (produto_id, slug, nome, descricao, imagem_grande, imagem_pequena,
                            preco_original, preco_promocional, desconto_oferta, padrao, vitrine, ordem)
SELECT pe.produto_id, 'basico', e.nome_venda, e.descricao, e.imagem_grande, e.imagem_pequena,
       pe.preco_original, pe.preco_promocional, p.desconto_oferta, 1, 1, 1
FROM plano_entregaveis pe
JOIN entregaveis e ON e.id = pe.entregavel_id
JOIN produtos p ON p.id = pe.produto_id
WHERE pe.papel = 'principal';

-- Produtos de app (apps_produto, migration 082): plano padrão com os dados do app.
INSERT INTO produto_planos (produto_id, slug, nome, descricao, imagem_grande, imagem_pequena,
                            preco_original, preco_promocional, desconto_oferta, padrao, vitrine, renovacao, ordem)
SELECT ap.produto_id, IF(ap.renovacao = 1, 'renovacao', 'basico'), ap.nome_venda, ap.descricao,
       ap.imagem_grande, ap.imagem_pequena, ap.preco_original, ap.preco_promocional, p.desconto_oferta,
       1, IF(ap.renovacao = 1, 0, 1), ap.renovacao, 1
FROM apps_produto ap
JOIN produtos p ON p.id = ap.produto_id
WHERE NOT EXISTS (SELECT 1 FROM produto_planos pp WHERE pp.produto_id = ap.produto_id);

-- Reserva: produto com vínculos (bônus/bump) mas sem principal nem app — plano padrão inativo, com o
-- nome/preço do produto, só para nenhum vínculo ficar sem plano (o checkout continua recusando).
INSERT INTO produto_planos (produto_id, slug, nome, preco_original, preco_promocional, padrao, vitrine, ativo, ordem)
SELECT DISTINCT pe.produto_id, 'basico', p.nome, p.preco, p.preco, 1, 0, 0, 1
FROM plano_entregaveis pe
JOIN produtos p ON p.id = pe.produto_id
WHERE NOT EXISTS (SELECT 1 FROM produto_planos pp WHERE pp.produto_id = pe.produto_id);

-- Todo vínculo de hoje pertence ao plano padrão do produto.
UPDATE plano_entregaveis pe
JOIN produto_planos pp ON pp.produto_id = pe.produto_id AND pp.padrao = 1
SET pe.plano_id = pp.id;

-- Um entregável "app" por app vendido (hoje só o Fatia).
INSERT INTO entregaveis (tipo, app_slug, nome_venda, descricao)
SELECT DISTINCT 'app', ap.app_slug,
       CASE ap.app_slug WHEN 'fatia' THEN 'App Fatias' ELSE CONCAT('App ', ap.app_slug) END,
       CASE ap.app_slug WHEN 'fatia' THEN 'Seu passo a passo para vender fatias de bolo' ELSE NULL END
FROM apps_produto ap
WHERE NOT EXISTS (SELECT 1 FROM entregaveis e WHERE e.tipo = 'app' AND e.app_slug = ap.app_slug);

-- O app é o principal do plano padrão dos produtos de app (com os dias de acesso).
INSERT INTO plano_entregaveis (produto_id, plano_id, entregavel_id, papel, preco_original, preco_promocional, ordem, dias)
SELECT ap.produto_id, pp.id, e.id, 'principal', 0.00, 0.00, 1, ap.dias
FROM apps_produto ap
JOIN produto_planos pp ON pp.produto_id = ap.produto_id AND pp.padrao = 1
JOIN entregaveis e ON e.tipo = 'app' AND e.app_slug = ap.app_slug;

-- Itens de app já vendidos (produto 16...): ligam ao vínculo do app, para a licença achar os dias.
UPDATE pedido_itens pi
JOIN pedidos p ON p.id = pi.pedido_id
JOIN plano_entregaveis pe ON pe.produto_id = p.produto_id AND pe.papel = 'principal'
JOIN entregaveis e ON e.id = pe.entregavel_id AND e.tipo = 'app' AND e.app_slug = pi.app_slug
SET pi.ebook_produto_id = pe.id
WHERE pi.app_slug IS NOT NULL AND pi.ebook_produto_id IS NULL;

-- Cada entregável uma vez por plano (um clique duplo no admin não duplica os itens de todo pedido).
ALTER TABLE plano_entregaveis
    MODIFY plano_id INT NOT NULL,
    ADD UNIQUE KEY uk_plano_entregaveis_item (plano_id, entregavel_id);

-- ---------------------------------------------------------------- pedido
ALTER TABLE pedidos
    ADD COLUMN plano_id INT NULL COMMENT 'Oferta comprada (produto_planos); NULL = pedidos anteriores' AFTER produto_id,
    ADD CONSTRAINT fk_pedidos_plano FOREIGN KEY (plano_id) REFERENCES produto_planos (id);

-- ---------------------------------------------------------------- compatibilidade (removida na 086)
-- Código antigo, entre esta migration e o rebuild dos containers, ainda lê ebooks/ebooks_produto.
CREATE OR REPLACE VIEW ebooks AS
    SELECT id, nome_venda, descricao, path_arquivo, nome_arquivo, imagem_grande, imagem_pequena, created_at
    FROM entregaveis WHERE tipo = 'ebook';
CREATE OR REPLACE VIEW ebooks_produto AS
    SELECT pe.id, pe.produto_id, pe.entregavel_id AS ebook_id, pe.papel, pe.preco_original,
           pe.preco_promocional, pe.ordem, pe.created_at
    FROM plano_entregaveis pe JOIN produto_planos pp ON pp.id = pe.plano_id AND pp.padrao = 1
    JOIN entregaveis e ON e.id = pe.entregavel_id AND e.tipo = 'ebook';
