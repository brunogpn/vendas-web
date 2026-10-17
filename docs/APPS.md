# Apps das clientes (PWA em `/app/<slug>/`)

Ferramentas web vendidas junto com os e-books, com acesso por tempo (licença). O primeiro é o
**App Fatias** (`/app/fatia/`), reescrito aqui a partir do projeto do Bruno (`brunogpn/saas-fatias`,
Next.js), que serviu de especificação. Regras e telas do Fatia: [APP_FATIA_ESPECIFICACAO.md](APP_FATIA_ESPECIFICACAO.md).

## Como funciona para a cliente

1. Compra no nosso checkout um plano que tem o app (ex.: Fatias que Vendem — Completo).
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
  __init__.py          lista de apps ativos (_MODULOS), APPS, apps_do_pedido(), registrar(flask)
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

## Venda e liberação: o app é um item de plano

O app é vendido como **item de um plano** do produto (ex.: plano Completo do Fatia = App Fatias + e-book +
bônus). Modelo, regras e admin: **[PLANOS.md](PLANOS.md)**. O que é específico do app:

- **Catálogo:** um entregável `tipo = 'app'` por app (`app_slug` = pasta em `app/apps/`). Os **dias** de
  acesso ficam no item do plano (`plano_entregaveis.dias`): o mesmo app pode dar 90 dias no Completo e
  365 numa renovação anual.
- **Liberação:** pelos itens app do pedido (`apps.apps_do_pedido`), nunca pelo produto — Básico não libera,
  Completo libera. Ponto único: início de `tasks.enviar_email_entrega` (todo pagamento web passa por lá).
  Idempotente pela PK `(pedido_id, app_slug)` de `apps_licenca_pedidos`. Redes de segurança: a rota
  "abrir app" também libera; `tasks.apps_reconciliar_licencas` (de hora em hora, :47) pega pedido pago com
  item app que ainda não liberou.
- **Depois do pagamento:** plano com app leva direto para o app, já logada
  (`/pedido2/<guid>/abrir-app/<slug>`); os outros continuam indo para a Estante.
- **Renovação = plano com `renovacao = 1`** (fora da vitrine): aparece em "Meu acesso" dentro do app. É um
  pedido novo (pagamento e NF-e próprios). Renovou antes de vencer → os dias somam a partir do vencimento
  atual; depois → a partir de hoje. O progresso no app é da cliente, não do pedido.
- **Só no site:** o plano padrão (o do WhatsApp, que entrega antes de cobrar) de produto com número de
  WhatsApp não pode ter app — o admin recusa.
- **Estante 2:** quem não tem o app vê um card dele no cross-sell (o plano com app mais caro, de preferência
  do mesmo produto do pedido); quem tem vê em "Meus apps".
- **Landing do Fatia** (`/fatia-e`): Básico = plano padrão do 12; Guiado = o plano com o App Fatias à venda
  (de vitrine, não renovação, de preferência do produto 12). Se ele tiver desconto de oferta, o clique no
  Básico abre o popup com o Guiado por esse preço. Sem plano com app, fica só o Básico.

### Desconto de oferta (popup do Básico e Estante 2)

O desconto fica no **plano** (`produto_planos.desconto_oferta`, admin → Planos e entregáveis → Editar plano).
Quem mostra a oferta gera um link com **token assinado** (`?oferta=`, `app/web/oferta.py`, vale 24 h e só
para aquele produto e plano): o popup "última tentativa" ao clicar no Básico do `/fatia-e` e o card do app
no cross-sell da Estante 2. `gerar_pix`/`gerar_cartao` validam o token e buscam o desconto no banco — sem
token, preço cheio. O checkout mostra "🎁 Desconto especial −R$ X" e o selo "Oferta aplicada"; o pedido
grava `pedidos.desconto` e o item principal já com desconto. NF-e, ROI e conversão do Ads usam o valor
pago. O quiz registra as etapas 18 (viu o popup) e 19/20 (recusou/aceitou) no Analytics Web.

### Piloto (antes de lançar)

`publico=False` no `config.py` do app (o Fatia começa assim): a landing dos anúncios (`/fatia-e`)
continua só com o Básico e a Estante não oferece o app; os dois planos aparecem só em
**`/fatia-e-piloto`** (fora do funil e dos buscadores) para homologação. Quem compra no piloto usa
tudo normalmente (e-mail, "Meus apps", app). Para lançar: `publico=True` e deploy.

### Checklist ao vender um app num produto

1. Catálogo de entregáveis: o app já existe? (o App Fatias sim). Senão, cadastrar `tipo = app`.
2. Produto → Planos e entregáveis: criar o plano (ex.: `completo`), "Copiar itens" do Básico e incluir o
   app como principal com os dias. Desconto de oferta, se houver popup/Estante.
3. **Chave PIX de venda web** e **planilhas do Google Ads** (por domínio) do produto — a tela de planos
   avisa em vermelho enquanto faltarem. Sem planilha, a venda não vira conversão.
4. Landing: link do botão para `/pay/<produto>?plano=<slug>` (no Fatia, `_planos_app_fatia` monta sozinho).

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
