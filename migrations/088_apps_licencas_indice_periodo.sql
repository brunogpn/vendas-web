-- Admin "Apps das clientes": a lista filtra as licenças por app e período de liberação (apps_licencas.criado_em),
-- paginada. Sem este índice, com dezenas de milhares de licenças, cada abertura leria a tabela inteira.
-- A busca do atendimento é pelo começo do e-mail (índice único já existente) ou do nome (índice novo).
ALTER TABLE apps_licencas ADD KEY idx_apps_licencas_app_criado (app_slug, criado_em);
ALTER TABLE apps_clientes ADD KEY idx_apps_clientes_nome (nome);
