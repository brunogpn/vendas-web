# Produto Música (Música de Presente)

A cliente responde um quiz sobre quem vai ganhar a música, uma IA escreve a letra, o gerador compõe 2 versões
e ela **ouve 40 s grátis de cada uma** antes de pagar. Pagou, recebe a música completa (ouvir, baixar) e os
itens que comprou. Veio do projeto do Bruno (`brunogpn/musica-presente`); a lógica de quiz, letra, geração,
prévia e videoclipe é dele, o encaixe (planos, checkout, pagamento, e-mail, Celery, Ads) é o do sistema.

## O que se vende (produto → planos → entregáveis, ver PLANOS.md)

Entregável `tipo = 'musica'` com um **recurso** (`entregaveis.recurso`, gravado também em `pedido_itens.recurso`),
como o `app_slug` dos apps. Lista em `app/musica/dominio/recursos.py`:

| Recurso | Papel no plano | O que libera |
|---|---|---|
| `musica` | principal | as 2 versões completas (ouvir, baixar, letra) |
| `videoclipe` | principal | fotos da cliente + música em vídeo vertical |
| `qrcode` | order bump | cartão para imprimir com o QR da página do presente |
| `entrega_email` | order bump | e-mail para quem recebe (agora ou na hora marcada), com cópia para quem comprou; **só o link** |
| `entrega_whatsapp` | order bump | preparado, **não vendido** (sem número de WhatsApp) |

Planos: **Música** (padrão) e **Música + Videoclipe**. Os preços são do plano e dos bumps (admin), nunca do código.
O admin recusa recurso no papel errado e item de música no plano padrão de produto com WhatsApp.

## O caminho da cliente

```
/musica/?ocasiao=mae  (landing; cria o rascunho 1004 com o GCLID)
  → /musica/criar     (quiz; e-mail obrigatório, WhatsApp opcional)
  → /musica/p/<token> (letra → ajustes → "criar a música" → espera → prévia → escolha do plano)
  → /pay/<produto>?plano=...&musica=<token>   (checkout de sempre, com os order bumps)
  → /musica/compra/<guid>   (quem comprou: ouvir/baixar, QR, presente por e-mail, fotos do videoclipe)
  → /musica/m/<token>       (o presente: só a música e o vídeo; é para onde o QR e o e-mail apontam)
```

- **Checkout:** plano de música só abre com `?musica=` de uma música com a prévia pronta, do mesmo produto e
  ainda não comprada; sem isso volta para a prévia. `gerar_pix`/`gerar_cartao` conferem de novo
  (`musica_invalida`) e gravam o vínculo em **`musica_pedidos`** (um pedido → uma música; a mesma música pode ter
  mais de um PIX, o primeiro pago libera, e pagamento em dobro avisa a equipe).
- **Liberação:** `tasks.enviar_email_entrega` chama `musica.liberar_do_pedido` (ponto único, como os apps). Redes de
  segurança: a página da compra e `musica.manutencao` (beat, 5 min). Liberada = `musicas.liberada_em` + `pedido_id`.
- **E-mail de entrega:** o mesmo do sistema, com o botão "🎵 Ouvir minha música" para a área da compra.
- **Presente por e-mail:** sempre com cópia (cc) para quem comprou. Se não chegar (erro no envio, ou devolução do
  servidor de quem recebe — quase sempre caixa lotada — que a leitura da caixa do `admin@` reconhece pelo thread do
  envio), tenta de novo: até **4 envios no mesmo dia**, esperando 1 h, 2 h e 4 h. Depois, quem comprou recebe o link
  para mandar por conta própria e a equipe é avisada. Devolução da cópia de quem comprou não gera reenvio.
- **Estante 2:** card "Minha música". A Música fica fora do cross-sell de e-books (a compra começa no quiz).
- **Google Ads:** o GCLID fica no rascunho da landing (`musicas.pedido_origem_id`); se a compra criar pedido novo
  (ex.: voltou pelo lembrete), ele herda a campanha. Conversão pelo fluxo de sempre (planilha), valor real pago.
- **Analytics Web:** página `musica` — quiz 1–15, letra 20, prévia 30, clique em comprar 40.
- **NF-e:** produto com `nfe_automatica = 0` (admin → dados básicos, só admin) fica fora da emissão diária, por PIX
  e cartão. **A Música precisa ficar assim** até a decisão fiscal (música não é livro).

## Arquitetura (`app/musica/`, portas e adaptadores)

```
dominio/        regras puras: modelos (status, resultados), regras (estilo, prévia, trava, presente),
                legenda (encaixe da letra), quiz, recursos
portas.py       GeradorMusica, EscritorLetra, Transcritor, Audio, Video, Repositorio, Agenda, Notificador
adaptadores/    gerador_apiframe (MVP) · gerador_suno (esqueleto) · gerador_simulado (dev/testes)
                letra_openai (+ LetraSimulada) · transcritor_openai · audio_ffmpeg · video_ffmpeg
                repositorio_mysql (todo o SQL) · agenda_celery · notificador (Gmail; WhatsApp desligado) · arquivos
fabrica.py      escolhe os adaptadores pelo .env — único lugar que conhece os provedores
casos_de_uso.py o fluxo inteiro; só fala com as portas
rotas.py        HTTP fino (erros jsonify 4xx, POST com origem_confiavel); tarefas.py: Celery fino
integracao.py   o que checkout, tasks, e-mail e Estante usam daqui
```

**Trocar a Apiframe por uma conta própria do Suno:** implementar os 3 métodos de `adaptadores/gerador_suno.py`
(`criar`, `consultar`, `webhook_valido`, devolvendo os objetos de `dominio/modelos.py`) e `MUSICA_GERADOR=suno`.
Nada mais muda. Antes, confirmar se existe acesso oficial do Suno por API para uso comercial.

**Letra:** a nossa integração OpenAI (`OPENAI_API_KEY`, `chat.completions`, saída `json_schema`), modelo em
`MUSICA_MODELO_LETRA` (padrão `gpt-6.1-sol`, o que venceu o teste do Bruno; testado em 17/10/2026 com o
`openai==1.59.7` atual). Regras de composição em `conteudo/instrucoes_letra.md`, estilos em `conteudo/estilos.json`.

**Filas:** letra na `urgente` (a cliente espera na tela); gerar/consultar (a cada 10 s, ou pelo webhook com
`MUSICA_URL_PUBLICA`), presentes e lembretes na `normal`; videoclipe e limpeza na `baixa` (concorrência 2 segura
o pico das datas fortes). Arquivos em `storage/musica/<token>/` (privado, volume do app e dos workers).

**Rotinas (beat):** `musica.manutencao` (5 min: presentes na hora marcada, destravar tarefa perdida, reconciliar
pagos), `musica.lembretes` (e-mail 1 h e 24 h depois da prévia não comprada, 8h–21h),
`musica.limpeza` (04h13: apaga músicas não compradas de 90+ dias, banco e disco — promessa da privacidade).

**Custo e abuso:** cada quiz custa uma letra na OpenAI e cada prévia uma geração (~11 créditos). Limites por e-mail
ou IP em 24 h: `MUSICA_LIMITE_LETRAS_DIA` (5 quizzes) e `MUSICA_LIMITE_PREVIAS_DIA` (3 músicas — conta só o que a
cliente pediu, "criar a música" e "outra versão"; as novas tentativas automáticas depois de falha do gerador não
contam). 1 "outra versão", 2 ajustes de letra. **Turnstile ligado em produção** (`TURNSTILE_*`; o app avisa no log
se faltar).

**Configuração:** o que é do produto fica no banco — qual produto vende (o ativo/à venda cujo plano padrão tem item
de música), preços, remetente e a **empresa** dos termos e da privacidade (a configuração fiscal ligada ao produto,
`nfe_config_id`: a LBE Livros; ligar não emite nota, porque `nfe_automatica = 0`). No `.env`, só provedores, chaves
e limites.

**Videoclipe:** o navegador reduz e envia **uma foto por vez** (cada uma < 900 KB), abaixo do limite de 1 MB do nginx
— não precisa mexer no nginx. Montagem perdida (worker reiniciado) é retomada uma vez pela manutenção.

## Rodar no dev

```bash
docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < migrations/089_musica.sql
# .env: MUSICA_GERADOR=simulado, MUSICA_LETRA_SIMULADA=1 (sem gastar crédito); o produto vem do banco
docker compose up -d --build app worker-urgente worker-normal worker-baixa beat && make reload-nginx
```

Abra `http://localhost/musica/`. No dev, os e-mails da Música só vão para o log. **Atenção:** o e-mail de
entrega do sistema (`entrega_pedido_email.py`) envia de verdade no dev — teste a confirmação de pagamento com um
e-mail seu. Testes: `pytest tests/musica`.

## Checklist para colocar no ar

1. Migrations **089** (estrutura) e **090** (cadastro do produto: 2 planos, 4 itens, empresa LBE, fora da NF-e,
   **disponível no site desligado**), depois `docker compose up -d --build app worker-urgente worker-normal
   worker-baixa beat` + `make reload-nginx`.
2. Admin → produto "Música de Presente": **chave PIX própria** de venda web (não a do produto 6), e-mail remetente
   (em "Enviar e-mail como" do `admin@`), e só então ligar "Disponível para venda no site".
3. `.env` de produção: `MUSICA_GERADOR=apiframe`, `APIFRAME_API_KEY` (a chave nova do Bruno), `TURNSTILE_SITE_KEY` e
   `TURNSTILE_SECRET` (Cloudflare, grátis; sem eles o app avisa no log), `MUSICA_URL_PUBLICA` opcional
   (`https://<domínio>`: a Apiframe avisa quando termina; sem ela, consulta a cada 10 s).
4. A Música abre em `/musica/` de **qualquer** domínio nosso. Para anunciar: planilha do Ads do produto por domínio.
5. Uma compra real de ponta a ponta antes dos anúncios.

## Pendências (Leo e Bruno)

NF-e (conversa à parte); Suno direto (existe API oficial?) e direitos de uso comercial; revisão dos termos e da
privacidade por advogado; preços; WhatsApp (número + modelos aprovados na Meta → `MUSICA_WHATSAPP_ATIVO=1` e
implementar o envio em `adaptadores/notificador.py`); jingle para empresas (etapa 4 do plano do Bruno).
