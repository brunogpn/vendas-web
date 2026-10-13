# App Fatias — especificação

App gamificado vendido com os e-books de fatias de bolo para feira (Ju Negreiros). Leva a cliente
do zero à primeira venda. Público: mulheres 40+, muitas desempregadas, pouca prática com internet —
letra e botões grandes, celular primeiro, "lucro" (nunca "margem"), suporte só por e-mail.

Origem: projeto do Bruno (`brunogpn/saas-fatias`, commit `67c819d`, 05/10/2026), reescrito no
vendas-web (ver [APPS.md](APPS.md)). Conteúdo (trilha, ingredientes, receitas, fotos) veio de lá.

## Telas (`/app/fatia/...`)

| Rota | O que faz |
|---|---|
| `entrar` | capa tomate com 3 fatias em leque; e-mail → código de 6 números (no dev o código aparece na tela) |
| `boas-vindas` | 5 perguntas (nome, meta R$ 1.000–10.000 ou outro, investimento, dias de venda, preço — padrão R$ 18) → "Seu plano está pronto" com fatias por semana + confete. Obrigatória no 1º acesso |
| `/` (início) | data por extenso, "Olá, {nome}", aviso de vencimento (≤ 7 dias), próxima tarefa, nível/pontos/sequência, lucro do mês × meta, fatias fáceis, medalhas |
| `tarefas`, `tarefas/<id>` | trilha de 38 passos em 5 fases; passo com texto, checklist (marcado no aparelho), mensagem pronta para copiar, dica, link para a ferramenta; "Terminei esta tarefa" → comemoração (confete + "plim") |
| `receitas`, `receitas/<id>` | 33 fatias + 10 brigadeiros; busca sem acento e filtro na URL; ficha, ingredientes marcáveis, preparo, versões (bases viram links), "usa / é usada por", página do PDF |
| `vendas` | lucro do mês, registro por dia (gastou, fatias, recebeu) com contas ao vivo e "guarde para as próximas compras"; dias anteriores |
| `precos` | "Meus preços": preço e embalagem de cada um dos 51 ingredientes |
| `calculadora` | custo da fatia (ingredientes + 10% gás/luz/perdas ÷ rendimento + embalagem), 3 preços sugeridos + outro, "Usar R$ X no app" |
| `lista` | receitas × vezes → ingredientes somados em embalagens inteiras, gasto previsto, carrinho marcável (salvo no servidor) |
| `mais`, `medalhas`, `perfil`, `acesso`, `ebooks` | menu; 15 medalhas e 5 níveis; dados e meta; validade e renovação; e-books da cliente (mesmos da Estante 2) |

## Regras (todas calculadas, nada de pontos/medalhas gravado)

- **Pontos:** 10 por tarefa, 5 por dia de venda lançado. **Níveis:** Aprendiz 0, Confeiteira 60,
  Feirante 150, Empreendedora 260, Mestra das Fatias 400.
- **Sequência:** dias seguidos com tarefa ou venda; hoje sem atividade ainda conta a de ontem.
- **Medalhas (15):** primeiro passo; uma por fase (5); primeira venda; 50 e 200 fatias; R$ 100 e
  R$ 1.000 de lucro; 3 e 7 dias seguidos; meta do mês; trilha completa.
- **Metas:** preço = informado ou 18; custo = o da calculadora ou 30% do preço; lucro por fatia =
  preço − custo (mínimo R$ 0,50); fatias/mês = ⌈meta ÷ lucro⌉; por dia de venda =
  ⌈fatias/mês ÷ (dias por semana × 4,3)⌉ (sem dias escolhidos, conta 2).
- **Trilha:** a ordem que vale é a da lista em `conteudo/trilha.json`; um passo libera o próximo;
  só o último concluído pode ser desmarcado. **Ids nunca são renumerados** (próximo livre: 39).
- **Vendas:** um registro por dia, data até hoje; lucro = recebido − gasto; "guardar" =
  min(fatias × custo, recebido).
- **Preços sugeridos:** maior entre "vezes o custo" e o mínimo de mercado — fatias 18/4×, 22/5×,
  26/6× (reais inteiros); brigadeiros 3/2×, 5/2,5×, 8/3× (de 50 em 50 centavos).
- **Lista de compras:** embalagens = ⌈qtd ÷ tamanho − 0,02⌉ (folga de 2%), mínimo 1.
- **Licença:** ver APPS.md. Vencida: vê tudo, não grava tarefas/vendas/preços/lista; perfil editável.

## Conteúdo

- `app/apps/fatia/conteudo/trilha.json` — fases e passos (campos: id, fase, icone, titulo, tempo,
  texto[], checklist?, mensagem?, link?, dica?). Links são relativos ao app (`/receitas`).
- `conteudo/ingredientes.json` — catálogo (id, nome, unidade g/ml/un, embalagem, rotuloEmbalagem, grupo).
- `conteudo/receitas/*.txt` — formato em `conteudo/receitas/LEIAME.md`; lido por `apps/fatia/receitas.py`,
  que **falha no import** se houver id repetido, ingrediente fora do catálogo, `usa:`/`{link}`
  inexistente ou linha não reconhecida (melhor quebrar no deploy do que mostrar receita pela metade).
- Fotos: `static/apps/fatia/receitas/<id>.jpg` (dos e-books e da Pexels; novas só Pexels/Unsplash).
- ⚠️ Validade e conservação vieram do e-book (gerado por IA): conferir antes de divulgar.

## Diferenças em relação ao original (melhorias)

1. `"1.000"` digitado vale mil (no original virava 1).
2. Concluir tarefa confere se o passo existe.
3. O "plano pronto" das boas-vindas usa a mesma conta de metas do app (no original era outra).
4. Perfil e boas-vindas conferem a resposta do servidor e mostram o erro.
5. "Vence hoje" em vez de "Faltam 0 dias".
6. Limpeza de sessões/códigos vencidos na rotina diária (não a cada pedido de código).
7. Limite de códigos também por IP (20/h), além de 5/h por e-mail; hashes com HMAC da SECRET_KEY.
8. Entrada sem código pela Estante 2 / e-mail de entrega / link do atendimento.
9. Tela "Meus e-books" ligando à Estante 2, e "Meus apps" na Estante.
10. Admin para atendimento (estender, trocar e-mail, link de acesso) e números de uso.
