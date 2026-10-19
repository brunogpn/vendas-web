-- Cadastro do produto Música (Música de Presente) para o piloto — rodar DEPOIS da 089.
-- Igual ao validado no dev (produto 20). Ajustes finos (preços, nomes, imagens) ficam no admin.
-- Idempotente: se o produto já existir (pelo nome), nada é inserido de novo.
--
-- O que NÃO vai aqui (fazer no admin depois de rodar):
--   * Chave PIX própria de venda web (Planos e entregáveis avisa em vermelho enquanto faltar) — sem ela o PIX
--     não é gerado. Não usar a do produto 6.
--   * E-mail remetente (precisa estar em "Enviar e-mail como" do Gmail do admin@).
--   * "Disponível para venda no site": entra DESLIGADO; ligar no admin quando a chave PIX estiver cadastrada.
--   * Planilha do Google Ads: só quando for anunciar.

SET NAMES utf8mb4;

-- Produto: fora da NF-e automática (música não é livro); empresa = LBE (só para os termos e a privacidade);
-- convênio BB igual ao dos outros produtos de venda web da LBE (sem ele o gerar_pix quebra).
INSERT INTO produtos (nome, preco, ativo, disponivel_web, nfe_automatica, nfe_config_id, numero_convenio_bb,
                      email_nome_remetente, email_cor_primaria, email_cor_secundaria)
SELECT 'Música de Presente', 29.90, 1, 0, 0,
       (SELECT id FROM nfe_configuracao WHERE tenant_slug = 'lbe-livros'),
       (SELECT numero_convenio_bb FROM produtos WHERE id = 12),
       'Música de Presente', '#E11D48', '#BE123C'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Música de Presente');

SET @produto = (SELECT id FROM produtos WHERE nome = 'Música de Presente');

-- Catálogo: um item por recurso (o recurso é o que o pagamento libera; ver app/musica/dominio/recursos.py).
INSERT INTO entregaveis (tipo, recurso, nome_venda, descricao)
SELECT 'musica', r.recurso, r.nome, r.descricao
FROM (SELECT 'musica' AS recurso, 'Sua música (2 versões)' AS nome,
             'As duas versões completas em MP3, com a letra' AS descricao
      UNION ALL SELECT 'videoclipe', 'Videoclipe com as suas fotos', 'Vídeo vertical para o Status e o Instagram'
      UNION ALL SELECT 'qrcode', 'Cartão com QR code', 'Imprima e entregue: a pessoa aponta a câmera e a música toca'
      UNION ALL SELECT 'entrega_email', 'Entrega por e-mail para quem vai receber',
                       'No dia e horário que você escolher, com cópia para você') r
WHERE NOT EXISTS (SELECT 1 FROM entregaveis e WHERE e.tipo = 'musica' AND e.recurso = r.recurso);

SET @e_musica = (SELECT MIN(id) FROM entregaveis WHERE tipo = 'musica' AND recurso = 'musica');
SET @e_video = (SELECT MIN(id) FROM entregaveis WHERE tipo = 'musica' AND recurso = 'videoclipe');
SET @e_qr = (SELECT MIN(id) FROM entregaveis WHERE tipo = 'musica' AND recurso = 'qrcode');
SET @e_email = (SELECT MIN(id) FROM entregaveis WHERE tipo = 'musica' AND recurso = 'entrega_email');

-- Planos: Música (padrão) e Música + Videoclipe. Preço "de" = preço cobrado (sem desconto inventado).
INSERT INTO produto_planos (produto_id, slug, nome, preco_original, preco_promocional, desconto_oferta,
                            padrao, vitrine, renovacao, ativo)
SELECT @produto, p.slug, p.nome, p.preco, p.preco, 0, p.padrao, 1, 0, 1
FROM (SELECT 'musica' AS slug, 'Música completa' AS nome, 29.90 AS preco, 1 AS padrao
      UNION ALL SELECT 'videoclipe', 'Música + Videoclipe', 49.90, 0) p
WHERE @produto IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM produto_planos pp WHERE pp.produto_id = @produto AND pp.slug = p.slug);

SET @plano_musica = (SELECT id FROM produto_planos WHERE produto_id = @produto AND slug = 'musica');
SET @plano_video = (SELECT id FROM produto_planos WHERE produto_id = @produto AND slug = 'videoclipe');

-- Itens: música como principal nos dois; videoclipe como principal só no plano com vídeo;
-- QR code (R$ 9,90) e entrega por e-mail (R$ 7,90) como order bumps nos dois.
INSERT INTO plano_entregaveis (produto_id, plano_id, entregavel_id, papel, preco_original, preco_promocional, ordem)
SELECT @produto, i.plano_id, i.entregavel_id, i.papel, i.preco, i.preco, i.ordem
FROM (SELECT @plano_musica AS plano_id, @e_musica AS entregavel_id, 'principal' AS papel, 0.00 AS preco, 1 AS ordem
      UNION ALL SELECT @plano_musica, @e_qr, 'bump', 9.90, 1
      UNION ALL SELECT @plano_musica, @e_email, 'bump', 7.90, 2
      UNION ALL SELECT @plano_video, @e_musica, 'principal', 0.00, 1
      UNION ALL SELECT @plano_video, @e_video, 'principal', 0.00, 2
      UNION ALL SELECT @plano_video, @e_qr, 'bump', 9.90, 1
      UNION ALL SELECT @plano_video, @e_email, 'bump', 7.90, 2) i
WHERE i.plano_id IS NOT NULL AND i.entregavel_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM plano_entregaveis pe WHERE pe.plano_id = i.plano_id AND pe.entregavel_id = i.entregavel_id);

-- Conferência (deve mostrar 1 produto, 2 planos e 7 itens):
SELECT p.id AS produto_id, p.nome, p.disponivel_web, p.nfe_automatica, p.nfe_config_id, p.numero_convenio_bb,
       (SELECT COUNT(*) FROM produto_planos WHERE produto_id = p.id) AS planos,
       (SELECT COUNT(*) FROM plano_entregaveis WHERE produto_id = p.id) AS itens
FROM produtos p WHERE p.id = @produto;
