# Produto → planos → entregáveis

O que o site vende, em três níveis (migrations 085/086, out/2026; a 087 transformou o antigo produto 16
"App Fatias — Plano Guiado" no plano `completo` do 12, com pedidos, licenças e PIX):

```
produtos             campanha, ISBN, NF-e, chave PIX, planilha do Google Ads, remetente do e-mail
 └─ produto_planos   as ofertas do produto: Básico, Completo, Renovação...
     │               nome, descrição, imagens, preço, desconto de oferta, padrão, vitrine, renovação
     └─ plano_entregaveis   o que o plano entrega: entregável + papel (principal / bônus / order bump)
          │                  preço próprio só no bump; `dias` só quando o item é app
          └─ entregaveis    catálogo único: e-book (arquivo PDF) ou app (`app_slug`, ver APPS.md)
pedidos.plano_id            qual plano foi comprado (NULL = pedidos de antes da 085)
pedido_itens                cópia dos itens do plano no momento da compra (ebook_produto_id → plano_entregaveis.id)
```

Exemplo do Fatia (produto 12):

| Plano | Link | Preço | Itens |
|---|---|---|---|
| Básico (padrão) | `/pay/12` | R$ 10 | 📖 Fatias que Vendem (principal) + 2 bônus + order bumps |
| Completo | `/pay/12?plano=completo` | R$ 22 (oferta R$ 15) | 📱 App Fatias 90 dias + 📖 Fatias que Vendem (principais) + os mesmos bônus e bumps |
| Renovação | `/pay/12?plano=renovacao` | — | 📱 App Fatias N dias (fora da vitrine; aparece em "Meu acesso" no app) |

A cliente compra **um plano**. A NF-e continua sendo do produto (livro, ISBN do produto) pelo valor pago.
Se o contador pedir o app como bônus do Completo, basta mudar o papel do item no admin.

## Regras

- **Preço:** o do plano. No pedido, o primeiro item principal leva o valor cobrado (com desconto, se houver);
  os demais principais e os bônus ficam com 0; cada bump leva o preço dele. Relatórios de receita usam
  `pedidos.valor_pago`.
- **Plano padrão:** 1 por produto (garantido no banco). É o do link sem `?plano=` e o dos pedidos do
  **WhatsApp** (que continua entregando o arquivo pelas ações do fluxo). Por isso o plano padrão de um
  produto com número de WhatsApp não pode ter app (lá a entrega vem antes do pagamento) — o admin recusa.
- **Plano à venda** = ativo e com pelo menos um item principal. Senão o checkout responde 404.
- **Vitrine:** planos que podem aparecer na landing e no cross-sell da Estante 2. Renovação nunca.
- **Order bumps são por plano** (`listar_bumps_validos(plano_id, ids)`): bump de outro plano é ignorado.
- **Desconto de oferta** (popup "última tentativa" da landing, cross-sell da Estante 2): no plano. O link
  leva um token assinado para **aquele produto e plano** (24 h, `app/web/oferta.py`); sem token, preço cheio.
  Desconto ≥ preço é ignorado (`desconto_valido`, regra única) e o admin não deixa salvar.
- **Retomada** (cookie do checkout): só reabre um pedido do **mesmo plano** (`pedido_do_plano`); comprou o
  Básico e abriu o Completo → pedido novo. Nova tentativa de cartão (1006/1007) idem.
- **App:** a licença sai dos **itens app do pedido**, com os `dias` do item no plano
  (`apps.apps_do_pedido`) — o Básico não libera app, o Completo libera. Depois do pagamento, plano com app
  leva direto para o app; o e-mail de entrega ganha o botão "Abrir meu App ...".
- **Estante 2:** cross-sell de e-book = plano padrão dos produtos cujo e-book principal ela não tem;
  cross-sell de app = um card por app que ela não tem (o plano mais caro, de preferência do mesmo produto
  do pedido), com o desconto de oferta do plano.
- **Google Ads:** venda do site (estado 1000) manda o valor real pago; WhatsApp (estado 0) manda R$ 10 fixo
  (o comprovante não é validado).

## Admin

- **Catálogo de entregáveis** (menu do admin): cadastre cada e-book (arquivo, capas) ou app uma vez.
- **Produto → Planos e entregáveis:** criar/editar planos (identificador do link, preços, desconto de oferta,
  imagens, vitrine, renovação, ativo), tornar padrão, incluir itens do catálogo (papel, preço do bump, dias
  do app), **copiar os itens de outro plano** (ex.: o Completo nasce do Básico + o app).
  - Item já vendido não sai do plano (os pedidos apontam para ele): crie outro plano e desative o antigo.
  - Plano já vendido não é removido: desative.
- **Clonar produto** copia os planos e os itens (não copia chave PIX, planilhas nem números de WhatsApp —
  a tela de planos avisa em vermelho o que falta).

## Código

`app/database.py` (bloco "Produto → planos → entregáveis"): `get_plano_venda`, `resolver_plano_checkout`,
`listar_entregaveis_plano`, `listar_bumps_validos`, `criar_itens_pedido_web`, `listar_planos_com_app`,
funções do admin. Checkout: `app/web/__init__.py` (`_plano_da_pagina`), `app/web/checkout.py`
(`gerar_pix`/`gerar_cartao` recebem `plano` no payload). Admin: `app/admin/planos_views.py`.
**Link para um plano:** sempre `web.links.link_checkout(produto_id, plano, ...)` (landing, Estante, "Meu acesso",
retomada, e-mail de follow-up) — nunca montar `/pay/<id>?plano=` à mão.
Retrato de regressão do checkout/Estante/e-mail: `tests/regressao/` (rodar antes e depois de mexer aqui).
