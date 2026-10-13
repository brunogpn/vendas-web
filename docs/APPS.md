# Apps das clientes (PWA em `/app/<slug>/`)

Ferramentas web vendidas junto com os e-books, com acesso por tempo (licença). O primeiro é o
**App Fatias** (`/app/fatia/`), reescrito aqui a partir do projeto do Bruno (`brunogpn/saas-fatias`,
Next.js), que serviu de especificação. Regras e telas do Fatia: [APP_FATIA_ESPECIFICACAO.md](APP_FATIA_ESPECIFICACAO.md).

## Como funciona para a cliente

1. Compra no nosso checkout um produto que dá o app (ex.: Plano Guiado).
2. O pagamento é confirmado → a licença é liberada (dias somados) → o e-mail de entrega leva o botão
   **"Abrir meu App Fatias"**, e a Estante 2 ganha a seção **"Meus apps"**.
3. O botão entra no app **já logada** (link de uso único). Depois, ela entra com o e-mail e um
   código de 6 números (sem senha).
4. Pode **instalar** na tela inicial (é um PWA: ícone, tela cheia). Não há loja (App Store/Play).
5. Licença vencida: continua entrando e vendo tudo, mas não grava nada novo (o perfil continua
   editável); aparece a faixa "Seu acesso venceu" e os avisos por e-mail 7 dias e 1 dia antes.

## Arquitetura

```
app/apps/
  __init__.py          lista de apps ativos (_MODULOS), APPS, apps_do_produto(), registrar(flask)
  _nucleo/             comum a todo app
    config_base.py     AppConfig (configuração em arquivo, por decisão: só vai p/ banco se validar)
    licenca.py         clientes (e-mail), licenças, liberar_licencas_do_pedido, reconciliar, ajustes do admin
    auth.py            código por e-mail, sessão (cookie apps_sessao, path /app/), link de uso único,
                       decorators pagina(cfg) / acao(cfg), checagem de Origin
    emails.py          código de login e aviso de vencimento (Gmail API; no dev NÃO envia, só loga)
    avisos.py          rotina diária: avisos de vencimento + limpeza
    estante.py         ligação com a Estante 2 ("Meus apps" lá, "Meus e-books" no app)
    rotas.py           /app/<slug>/entrar, /entrar/link/<token>, /sair, manifest, sw.js,
                       /pedido2/<guid>/abrir-app/<slug>
    datas.py, formato.py, urls.py
  <slug>/              um app (ex.: fatia/): config.py, rotas.py, dados.py, regras, conteudo/
  templates/apps/      _nucleo/ (base, entrar, componentes) e <slug>/
static/apps/_nucleo/   app.css (tokens/componentes), app.js (post, comemoração, confete, som), icones.svg, confetti
static/apps/<slug>/    JS do app, fotos, ícones do PWA
migrations/080_apps_nucleo.sql, 081_app_fatia.sql
```

- **Front:** Jinja + JS puro (sem framework), como as landings. Telas montadas no servidor; o que
  precisa ser ao vivo (calculadora, lista de compras, vendas) é JS na própria página.
- **Ações:** `POST` JSON (`App.post`) → `{ok, erro?, conquistas?}`. Erros sempre como
  `jsonify(...), 4xx` — nunca `abort()` (o handler global transforma em 500 e notifica no WhatsApp).
- **CSRF:** o projeto não tem token; os POST dos apps exigem `Origin`/`Referer` do próprio host e o
  cookie é `SameSite=Lax`.
- **PWA:** `manifest.webmanifest` e `sw.js` são rotas Flask dentro de `/app/<slug>/` (em `/static`
  o escopo do service worker ficaria errado). O SW só permite instalar; não há modo offline.

## Venda e liberação: o app é um produto

- **Produto do tipo app** (migration 082, tabela `apps_produto`): no admin, em *Produto → E-books do
  produto → "Tipo do produto"*, escolha o app, os dias, o nome de venda, os preços e a imagem. Sem
  linha em `apps_produto` o produto é de e-book (o padrão). Um produto é um OU outro.
- O app é o **principal**; os e-books (ex.: os do Fatia) entram como **bônus/order bump** normais.
  `get_ebook_principal_produto` devolve o app no lugar do e-book, então checkout (`/pay`, `/pay2`),
  PIX/cartão, `pedido_itens` (item principal com `app_slug` e sem arquivo) e NF-e seguem o mesmo caminho.
- **Ofertas:** cada combinação é um produto (Plano Guiado R$ 22, desconto R$ 15, só o app…).
  `renovacao = 1` marca as ofertas de renovação: aparecem em "Meu acesso" dentro do app; as demais
  aparecem no cross-sell da Estante 2 para quem ainda não tem o app (um card por app, o mais barato).
- **Depois do pagamento:** o checkout leva direto para o app, já logada (`/pedido2/<guid>/abrir-app/<slug>`);
  produto de e-book continua indo para a Estante.
- **Renovação = pedido novo** (pagamento e NF-e próprios). Renovou antes de vencer → os dias somam a
  partir do vencimento atual; depois → a partir de hoje. O progresso no app é da cliente, não do pedido.
- Ponto único de liberação: início de `tasks.enviar_email_entrega` (todo pagamento web passa por lá).
  Idempotente pela PK `(pedido_id, app_slug)` de `apps_licenca_pedidos`. Redes de segurança: a rota
  "abrir app" também libera; `tasks.apps_reconciliar_licencas` (de hora em hora, :47) pega o que faltou.
- **Só no site:** produto de app não deve ser vendido pelo WhatsApp (lá entrega antes de cobrar).
- **Landing do Fatia** (`/fatia-e`): se houver produto de app do Fatia à venda (e não renovação), a
  página mostra Básico + Plano Guiado (o mais caro); havendo um segundo mais barato, ele vira o popup
  de desconto ao clicar no Básico. Sem nenhum, fica só o Básico, como antes.

### Checklist ao criar um produto de app em produção

1. Criar o produto (pode clonar o 12) e marcar *disponível web* quando estiver pronto.
2. *E-books do produto*: remover o e-book principal (se clonou) → "Tornar este produto um app" → vincular
   os e-books como bônus/bump.
3. **Chave PIX de venda web** e **planilhas do Google Ads** (por domínio) — a clonagem NÃO copia; a tela
   do produto de app mostra um aviso vermelho enquanto faltarem. Sem planilha, a venda não vira conversão.
4. Valor da conversão: `fluxo_upload_google_ads.py` ainda manda valor fixo (20 para o produto 12, 10 para
   os demais) — decidir se o app usa o valor real.

## Domínio

O ícone instalado e o cookie de sessão ficam presos ao domínio, então tudo converge para um só: o
domínio oficial do app (`config.dominio`; no Fatia, `APP_FATIA_DOMINIO`) ou, vazio, o `APP_BASE_URL`
(MVP). Em produção o botão da Estante (de qualquer domínio nosso) e os e-mails levam para ele; no dev
fica no mesmo host (o `APP_BASE_URL` do dev aponta para o site real).
O domínio precisa estar ativo no nginx (skill `novo-dominio`) — o app é servido pelo mesmo Flask.

## Admin

`/admin/apps` (menu "Apps das clientes", só admin): números por app, busca por e-mail, liberar
acesso manual (cortesia/teste), e na página da cliente: somar dias ou definir vencimento, trocar
e-mail de acesso, **gerar link de acesso** (uso único, 3 dias) para o atendimento mandar.

## Rodar no dev

```bash
# migrations (uma vez)
docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < migrations/080_apps_nucleo.sql
docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < migrations/081_app_fatia.sql
docker compose up -d --build app && make reload-nginx
```

Crie uma cliente em `/admin/apps` → "Liberar acesso manualmente" e entre em
`http://localhost/app/fatia/entrar`: no dev o código aparece na própria tela (nenhum e-mail sai).
Testes: `pytest tests/apps`.

## Criar um app novo

1. `app/apps/<slug>/config.py` com `CONFIG = AppConfig(...)` e `rotas.py` com um Blueprint `bp`
   (`url_prefix=CONFIG.prefixo`), usando `auth.pagina(CONFIG)` nas telas e `auth.acao(CONFIG)` nas ações.
2. Templates em `app/apps/templates/apps/<slug>/` estendendo `apps/_nucleo/base.html`
   (opcional: `entrar.html` próprio estendendo `apps/_nucleo/entrar.html`).
3. Migration com as tabelas `app_<slug>_*` (FK para `apps_clientes`).
4. Incluir `'<slug>'` em `_MODULOS` (`app/apps/__init__.py`), ícones 192/512 em `static/apps/<slug>/`.

## Ícones

`static/apps/_nucleo/icones.svg` reúne os ícones Phosphor (MIT) usados: `<Nome>` (regular) e
`<Nome>-fill`. Uso nos templates: `ui.ic('Cake')`, `ui.ic('Cake', '', true)`; no JS: `App.icone('Cake')`.
Para incluir um ícone, baixe `regular/<nome>.svg` e `fill/<nome>-fill.svg` de
`cdn.jsdelivr.net/npm/@phosphor-icons/core@2.1.1/assets/` e acrescente como `<symbol>`.

## Pendências de negócio (Leo e Bruno)

Preços e dias do Plano Guiado e das renovações (agora é só cadastro de produto); domínio oficial
(MVP: `APP_BASE_URL`); ícones definitivos (os atuais são provisórios); valor da conversão no Google Ads.
