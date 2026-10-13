-- Núcleo dos "apps" das clientes (PWA em /app/<slug>/, ex.: App Fatias). Ver docs/APPS.md.
-- Tudo aqui é comum a qualquer app: quem é a cliente (e-mail), a licença de cada app (válida até
-- uma data), o login por código no e-mail, as sessões, o link de entrada de uso único (vindo da
-- Estante 2 / do checkout), os avisos de vencimento e um registro de acesso por dia (painel).
-- As tabelas de cada app ficam em migrations próprias, com prefixo app_<slug>_.

-- Cliente dos apps = e-mail normalizado (trim + minúsculo). Não existe tabela de cliente no resto
-- do sistema (o "cliente" lá é o pedido); aqui o e-mail é a chave do login.
CREATE TABLE IF NOT EXISTS apps_clientes (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(255) NOT NULL,
    nome       VARCHAR(120) NULL COMMENT 'Nome vindo da compra (a cliente pode mudar no app)',
    criado_em  TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_apps_clientes_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Licença de uma cliente num app. Ativa enquanto expira_em >= hoje (o dia do vencimento ainda vale).
CREATE TABLE IF NOT EXISTS apps_licencas (
    id               INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    cliente_id       INT         NOT NULL,
    app_slug         VARCHAR(40) NOT NULL COMMENT 'Ex: fatia',
    expira_em        DATE        NOT NULL,
    ultimo_acesso_em TIMESTAMP   NULL,
    criado_em        TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em    TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_apps_licencas_cliente_app (cliente_id, app_slug),
    KEY idx_apps_licencas_expira (app_slug, expira_em),
    CONSTRAINT fk_apps_licencas_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- O que somou dias numa licença. A PK (pedido_id, app_slug) é a trava de idempotência: o mesmo
-- pedido pago nunca soma duas vezes, por mais que a liberação seja chamada de vários lugares.
-- pedido_id NULL não é permitido na PK, então ajustes manuais do admin vão para apps_licenca_ajustes.
CREATE TABLE IF NOT EXISTS apps_licenca_pedidos (
    pedido_id   INT           NOT NULL,
    app_slug    VARCHAR(40)   NOT NULL,
    cliente_id  INT           NOT NULL,
    produto_id  INT           NOT NULL,
    dias        INT           NOT NULL,
    valor       DECIMAL(10,2) NULL,
    expira_antes DATE         NULL COMMENT 'Vencimento antes desta compra (NULL = licença nova)',
    expira_depois DATE        NOT NULL,
    criado_em   TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pedido_id, app_slug),
    KEY idx_apps_licenca_pedidos_cliente (cliente_id, app_slug),
    CONSTRAINT fk_apps_licenca_pedidos_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id),
    CONSTRAINT fk_apps_licenca_pedidos_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Ajustes feitos à mão no admin (estender dias, liberar cortesia, trocar e-mail), para histórico.
CREATE TABLE IF NOT EXISTS apps_licenca_ajustes (
    id          INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    cliente_id  INT          NOT NULL,
    app_slug    VARCHAR(40)  NOT NULL,
    acao        VARCHAR(30)  NOT NULL COMMENT 'estender | trocar_email | link_acesso',
    detalhe     VARCHAR(255) NULL,
    usuario_admin VARCHAR(120) NULL,
    criado_em   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_apps_licenca_ajustes_cliente (cliente_id),
    CONSTRAINT fk_apps_licenca_ajustes_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Código de login (6 dígitos) — um por e-mail; pedir de novo substitui e zera as tentativas.
-- Só o hash fica gravado.
CREATE TABLE IF NOT EXISTS apps_codigos_login (
    email        VARCHAR(255) NOT NULL PRIMARY KEY,
    codigo_hash  CHAR(64)     NOT NULL,
    expira_em    DATETIME     NOT NULL,
    tentativas   TINYINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cada pedido de código (para limitar por e-mail e por IP na última hora).
CREATE TABLE IF NOT EXISTS apps_pedidos_codigo (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(255) NOT NULL,
    ip         VARCHAR(45)  NULL,
    criado_em  DATETIME     NOT NULL,
    KEY idx_apps_pedidos_codigo_email (email, criado_em),
    KEY idx_apps_pedidos_codigo_ip (ip, criado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sessão (cookie httpOnly). Só o hash do token fica gravado.
CREATE TABLE IF NOT EXISTS apps_sessoes (
    token_hash CHAR(64)  NOT NULL PRIMARY KEY,
    cliente_id INT       NOT NULL,
    expira_em  DATETIME  NOT NULL,
    criado_em  TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_apps_sessoes_cliente (cliente_id),
    KEY idx_apps_sessoes_expira (expira_em),
    CONSTRAINT fk_apps_sessoes_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Link de entrada sem código (Estante 2, checkout, admin). Uso único e vence em minutos.
CREATE TABLE IF NOT EXISTS apps_links_entrada (
    token_hash CHAR(64)    NOT NULL PRIMARY KEY,
    cliente_id INT         NOT NULL,
    app_slug   VARCHAR(40) NOT NULL,
    expira_em  DATETIME    NOT NULL,
    usado_em   DATETIME    NULL,
    criado_em  TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_apps_links_entrada_expira (expira_em),
    CONSTRAINT fk_apps_links_entrada_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Aviso de vencimento já enviado (um por licença, tipo e data de vencimento: renovar gera avisos novos).
CREATE TABLE IF NOT EXISTS apps_avisos_enviados (
    licenca_id INT         NOT NULL,
    tipo       VARCHAR(10) NOT NULL COMMENT '7dias | 1dia',
    expira_em  DATE        NOT NULL,
    enviado_em TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (licenca_id, tipo, expira_em),
    CONSTRAINT fk_apps_avisos_enviados_licenca FOREIGN KEY (licenca_id) REFERENCES apps_licencas (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dias em que a cliente abriu cada app (uma linha por dia) — base do painel "ativas nos últimos 7 dias".
CREATE TABLE IF NOT EXISTS apps_acessos_dia (
    cliente_id INT         NOT NULL,
    app_slug   VARCHAR(40) NOT NULL,
    data       DATE        NOT NULL,
    PRIMARY KEY (cliente_id, app_slug, data),
    KEY idx_apps_acessos_dia_data (app_slug, data),
    CONSTRAINT fk_apps_acessos_dia_cliente FOREIGN KEY (cliente_id) REFERENCES apps_clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
