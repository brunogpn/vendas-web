-- Desconto de oferta: um valor cadastrado no produto que é abatido do preço do principal quando a
-- cliente chega ao checkout por uma oferta (popup "última tentativa" da landing, cross-sell da
-- Estante 2). A oferta é provada por um token assinado no link (ver app/web/oferta.py) — sem token,
-- preço cheio. O desconto efetivamente aplicado fica gravado no pedido.

-- Quanto a oferta abate do preço do principal (app ou e-book). 0 = produto sem oferta.
ALTER TABLE produtos
    ADD COLUMN desconto_oferta DECIMAL(10,2) NOT NULL DEFAULT 0.00
        COMMENT 'Desconto (R$) da oferta do popup/Estante sobre o preço do principal; 0 = sem oferta';

-- Desconto aplicado neste pedido (0 = preço cheio). valor_pago continua sendo o valor recebido.
ALTER TABLE pedidos
    ADD COLUMN desconto DECIMAL(10,2) NOT NULL DEFAULT 0.00
        COMMENT 'Desconto de oferta aplicado (R$); 0 = sem desconto' AFTER valor_pago;
