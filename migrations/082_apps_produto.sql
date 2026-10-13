-- Produto do tipo app: em vez de um e-book principal, o produto vende o acesso a um app
-- (ex.: App Fatias) por N dias. Uma linha aqui = "este produto é um app" (sem linha = e-book, o
-- padrão). Os e-books do app entram como bônus/bump normais em ebooks_produto, e o checkout,
-- o PIX/cartão e a NF-e funcionam igual — get_ebook_principal_produto devolve o app no lugar do
-- e-book principal (ver database.py). Ver docs/APPS.md.
CREATE TABLE IF NOT EXISTS apps_produto (
    produto_id        INT           NOT NULL PRIMARY KEY,
    app_slug          VARCHAR(40)   NOT NULL COMMENT 'Qual app libera (pasta app/apps/<slug>)',
    dias              INT           NOT NULL COMMENT 'Dias de acesso que a compra soma na licença',
    renovacao         TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '1 = oferta de renovação (aparece em "Meu acesso", não no cross-sell)',
    nome_venda        VARCHAR(255)  NOT NULL COMMENT 'Nome mostrado no checkout, na Estante e na NF-e do item',
    descricao         TEXT          NULL,
    imagem_grande     VARCHAR(255)  NULL COMMENT 'Arquivo em static/images/ (como as capas dos e-books)',
    imagem_pequena    VARCHAR(255)  NULL,
    preco_original    DECIMAL(10,2) NOT NULL,
    preco_promocional DECIMAL(10,2) NOT NULL COMMENT 'Valor cobrado',
    criado_em         TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_apps_produto_slug (app_slug),
    CONSTRAINT fk_apps_produto_produto FOREIGN KEY (produto_id) REFERENCES produtos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- O item principal de um produto app não tem PDF: arquivo passa a ser opcional e o item guarda
-- qual app foi vendido. Itens existentes não mudam.
ALTER TABLE pedido_itens
    MODIFY path_arquivo VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    MODIFY nome_arquivo VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
    ADD COLUMN app_slug VARCHAR(40) NULL COMMENT 'Preenchido no item principal de um produto do tipo app' AFTER ebook_produto_id;
