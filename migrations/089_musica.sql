-- Produto "Música" (Música de Presente, docs/MUSICA.md): a cliente faz o quiz, a IA escreve a letra, o gerador
-- (Apiframe → Suno no MVP) faz 2 versões, ela ouve a prévia grátis, paga um plano e recebe a música.
--
-- 1) Trava de NF-e: a rotina diária emite NF-e de LIVRO para todo PIX da chave do tenant, sem olhar o produto.
--    Música não é livro: produto com nfe_automatica = 0 fica fora da emissão automática (cartão e PIX) até a
--    decisão fiscal. Todos os produtos atuais continuam com 1 (nada muda para eles).
ALTER TABLE produtos
    ADD COLUMN nfe_automatica TINYINT(1) NOT NULL DEFAULT 1
        COMMENT '0 = fora da emissão automática de NF-e (ex.: Música, que não é livro)';

-- 2) Catálogo: entregável do tipo música. `recurso` diz o que ele libera (como app_slug faz para os apps):
--    musica (principal), videoclipe (principal do plano com vídeo), qrcode e entrega_email (order bumps),
--    entrega_whatsapp (preparado, sem venda por enquanto).
ALTER TABLE entregaveis
    MODIFY tipo ENUM('ebook','app','musica') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ebook',
    ADD COLUMN recurso VARCHAR(40) COLLATE utf8mb4_unicode_ci NULL
        COMMENT 'Quando tipo=musica: musica | videoclipe | qrcode | entrega_email | entrega_whatsapp'
        AFTER app_slug;

-- Fotografia do recurso no item do pedido (o que a cliente comprou), igual a app_slug.
ALTER TABLE pedido_itens
    ADD COLUMN recurso VARCHAR(40) COLLATE utf8mb4_unicode_ci NULL
        COMMENT 'Item de música: recurso comprado (entregaveis.recurso)'
        AFTER app_slug;

-- 3) A música da cliente. Nasce no quiz (antes de pagar, ligada ao pedido rascunho da landing quando houver)
--    e é liberada quando o pedido é pago. Arquivos em storage/musica/<token>/ (privado).
--    O checkout grava em musica_pedidos qual música cada pedido compra (a mesma visita pode criar várias
--    músicas, e a cliente pode gerar mais de um PIX para a mesma). musicas.pedido_id = o pedido PAGO que a
--    liberou. pedido_origem_id = rascunho da landing (funil, GCLID).
CREATE TABLE musicas (
    id                 INT NOT NULL AUTO_INCREMENT,
    token              CHAR(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Identificador público (URLs, QR code)',
    produto_id         INT NOT NULL,
    pedido_id          INT NULL COMMENT 'Pedido pago que liberou esta música',
    pedido_origem_id   INT NULL COMMENT 'Pedido rascunho da landing em que a música nasceu (funil)',
    dominio            VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL COMMENT 'Host em que a cliente criou (links dos e-mails)',
    status             VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL
        COMMENT 'escrevendo | letra_pronta | erro_letra | gerando | processando | previa_pronta | erro',
    respostas          JSON NOT NULL COMMENT 'Respostas do quiz',
    email              VARCHAR(200) COLLATE utf8mb4_unicode_ci NULL,
    whatsapp           VARCHAR(20) COLLATE utf8mb4_unicode_ci NULL,
    ip                 VARCHAR(45) COLLATE utf8mb4_unicode_ci NULL,
    titulo             VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    letra_exibicao     TEXT COLLATE utf8mb4_unicode_ci NULL,
    letra_suno         TEXT COLLATE utf8mb4_unicode_ci NULL,
    estilo             VARCHAR(1000) COLLATE utf8mb4_unicode_ci NULL,
    modelo_letra       VARCHAR(60) COLLATE utf8mb4_unicode_ci NULL COMMENT 'Modelo de IA que escreveu a letra',
    ajustes_letra      INT NOT NULL DEFAULT 0,
    provedor           VARCHAR(20) COLLATE utf8mb4_unicode_ci NULL COMMENT 'Gerador usado: apiframe | suno | simulado',
    job_id             VARCHAR(64) COLLATE utf8mb4_unicode_ci NULL,
    gerando_desde      DATETIME NULL,
    geracoes           INT NOT NULL DEFAULT 0 COMMENT 'Quantas vezes mandamos gerar (cada uma custa crédito)',
    outras_versoes     INT NOT NULL DEFAULT 0,
    faixas             JSON NULL COMMENT '[{numero, duracao}]',
    erro               TEXT COLLATE utf8mb4_unicode_ci NULL,
    liberada_em        DATETIME NULL COMMENT 'Pedido pago: a música completa está liberada',
    video_status       VARCHAR(20) COLLATE utf8mb4_unicode_ci NULL COMMENT 'fazendo | pronto | erro',
    video_versao       TINYINT NULL,
    video_legenda      TINYINT(1) NULL,
    video_erro         TEXT COLLATE utf8mb4_unicode_ci NULL,
    presente_nome      VARCHAR(120) COLLATE utf8mb4_unicode_ci NULL COMMENT 'Entrega por e-mail: quem recebe',
    presente_email     VARCHAR(200) COLLATE utf8mb4_unicode_ci NULL,
    presente_mensagem  VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    presente_em        DATETIME NULL COMMENT 'Quando enviar (horário de Brasília)',
    presente_enviado_em DATETIME NULL,
    presente_tentativas TINYINT NOT NULL DEFAULT 0 COMMENT 'Envios do presente já feitos (máx. 4, ver casos_de_uso)',
    presente_thread_id VARCHAR(32) COLLATE utf8mb4_unicode_ci NULL COMMENT 'Thread do Gmail do último envio (acha a devolução)',
    presente_falhou_em DATETIME NULL COMMENT 'Desistiu após as tentativas: quem comprou foi avisado',
    lembrete1_em       DATETIME NULL COMMENT 'Lembrete de 1 h para quem ouviu a prévia e não comprou',
    lembrete2_em       DATETIME NULL COMMENT 'Lembrete de 24 h',
    criado_em          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_musicas_token (token),
    UNIQUE KEY uk_musicas_pedido (pedido_id),
    KEY idx_musicas_origem (pedido_origem_id),
    KEY idx_musicas_job (job_id),
    KEY idx_musicas_email (email, criado_em),
    KEY idx_musicas_ip (ip, criado_em),
    KEY idx_musicas_status (status, criado_em),
    KEY idx_musicas_presente (presente_em, presente_enviado_em),
    KEY idx_musicas_presente_thread (presente_thread_id),
    CONSTRAINT fk_musicas_produto FOREIGN KEY (produto_id) REFERENCES produtos (id),
    CONSTRAINT fk_musicas_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE SET NULL,
    CONSTRAINT fk_musicas_pedido_origem FOREIGN KEY (pedido_origem_id) REFERENCES pedidos (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Qual música cada pedido do checkout compra (gravado no gerar_pix/gerar_cartao; uma música por pedido).
CREATE TABLE musica_pedidos (
    pedido_id  INT NOT NULL,
    musica_id  INT NOT NULL,
    criado_em  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pedido_id),
    KEY idx_musica_pedidos_musica (musica_id),
    CONSTRAINT fk_musica_pedidos_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE,
    CONSTRAINT fk_musica_pedidos_musica FOREIGN KEY (musica_id) REFERENCES musicas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
