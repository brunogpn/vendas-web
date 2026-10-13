-- Tabelas do App Fatias (/app/fatia/). Ver docs/APP_FATIA_ESPECIFICACAO.md.
-- Pontos, níveis, medalhas e sequência NÃO ficam gravados: são calculados das tarefas e vendas.

-- Respostas das boas-vindas e preferências da cliente.
CREATE TABLE IF NOT EXISTS app_fatia_perfis (
    cliente_id    INT           NOT NULL PRIMARY KEY,
    nome          VARCHAR(60)   NULL,
    meta_mensal   DECIMAL(10,2) NULL COMMENT 'Lucro que quer por mês (padrão no app: 1000)',
    investimento  DECIMAL(10,2) NULL COMMENT 'Quanto pode gastar para começar',
    dias_venda    VARCHAR(40)   NULL COMMENT 'CSV: seg,ter,qua,qui,sex,sab,dom',
    preco_fatia   DECIMAL(10,2) NULL COMMENT 'Padrão no app: 18',
    custo_fatia   DECIMAL(10,2) NULL COMMENT 'Gravado pela calculadora; NULL = estimado (30% do preço)',
    onboarding_ok TINYINT(1)    NOT NULL DEFAULT 0,
    som           TINYINT(1)    NOT NULL DEFAULT 1,
    atualizado_em TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_app_fatia_perfis_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Passos da trilha concluídos (tarefa_id = id do passo em conteudo/trilha.json; ids nunca são renumerados).
CREATE TABLE IF NOT EXISTS app_fatia_tarefas_concluidas (
    cliente_id   INT      NOT NULL,
    tarefa_id    SMALLINT NOT NULL,
    concluida_em DATE     NOT NULL,
    PRIMARY KEY (cliente_id, tarefa_id),
    CONSTRAINT fk_app_fatia_tarefas_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Um registro por dia: quanto gastou, quantas fatias vendeu, quanto recebeu.
CREATE TABLE IF NOT EXISTS app_fatia_lancamentos (
    cliente_id    INT           NOT NULL,
    data          DATE          NOT NULL,
    gasto         DECIMAL(10,2) NOT NULL DEFAULT 0,
    fatias        INT           NOT NULL DEFAULT 0,
    recebido      DECIMAL(10,2) NOT NULL DEFAULT 0,
    atualizado_em TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (cliente_id, data),
    CONSTRAINT fk_app_fatia_lancamentos_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- "Meus preços": preço pago e tamanho da embalagem de cada ingrediente (item = id em conteudo/ingredientes.json).
CREATE TABLE IF NOT EXISTS app_fatia_precos (
    cliente_id INT           NOT NULL,
    item       VARCHAR(40)   NOT NULL,
    preco      DECIMAL(10,2) NOT NULL,
    quantidade DECIMAL(10,2) NOT NULL COMMENT 'Tamanho da embalagem na unidade do ingrediente (g, ml, un)',
    PRIMARY KEY (cliente_id, item),
    CONSTRAINT fk_app_fatia_precos_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Lista de compras atual: {"receitas": {id: vezes}, "marcados": [chaves dos itens no carrinho]}.
CREATE TABLE IF NOT EXISTS app_fatia_lista_compras (
    cliente_id    INT       NOT NULL PRIMARY KEY,
    dados         JSON      NOT NULL,
    atualizado_em TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_app_fatia_lista_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
