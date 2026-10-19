"""Perguntas do quiz. Para mudar texto, ordem ou opções, edite só esta lista.

Tipos: "opcoes" (botões), "texto" (uma linha), "texto_longo" (caixa grande), "contato".
O campo "chave" é o nome que vai para a IA da letra.

Os textos podem usar estas marcas, trocadas na tela pelas respostas anteriores:
    {nome}       apelido (se tiver) ou nome. Ex.: "Dona Lena"
    {primeiro}   o nome escrito na pergunta do nome. Ex.: "Helena"
    {da_sua_pessoa} "da sua mãe", "do seu pai"... ou "de quem vai receber"
    {ela}        "ela", "ele" ou "essa pessoa"
    {dela}       "dela", "dele" ou "dessa pessoa"
    {de}         o nome de quem dá o presente
"""

PERGUNTAS = [
    {
        "chave": "para_quem", "tipo": "opcoes",
        "titulo": "Pra quem é a música?",
        "opcoes": ["Mãe", "Pai", "Esposa", "Marido", "Namorada", "Namorado", "Filho", "Filha",
                   "Irmã", "Irmão", "Avó", "Avô", "Amiga", "Amigo", "Chefe", "Outra pessoa"],
    },
    {
        "chave": "nome", "tipo": "texto",
        "titulo": "Qual o nome {da_sua_pessoa}?",
        "ajuda": "Esse nome vai aparecer na letra da música.",
        "exemplo": "Ex.: Helena",
        "obrigatoria": True,
    },
    {
        "chave": "apelido", "tipo": "texto",
        "titulo": "Você chama {primeiro} por algum apelido carinhoso?",
        "ajuda": "Se tiver, a música usa o apelido no refrão.",
        "exemplo": "Ex.: Dona Lena, Ju, Mozão (pode deixar em branco)",
    },
    {
        "chave": "pronuncia", "tipo": "texto",
        "titulo": "O nome {primeiro} se fala diferente do jeito que se escreve?",
        "ajuda": "Ajuda a música a cantar o nome certinho.",
        "exemplo": "Ex.: Theo → Téo, Ingrid → Íngrid (pode deixar em branco)",
    },
    {
        "chave": "ocasiao", "tipo": "opcoes",
        "titulo": "Qual é a ocasião da música de {nome}?",
        "opcoes": ["Aniversário", "Dia das Mães", "Dia dos Pais", "Dia dos Namorados", "Casamento",
                   "Pedido de casamento", "Pedido de desculpas", "Chá revelação", "Formatura",
                   "Homenagem a quem já partiu", "Só porque eu amo"],
    },
    {
        "chave": "lembrancas", "tipo": "texto_longo",
        "titulo": "Conte 2 ou 3 lembranças especiais com {nome}",
        "ajuda": "É isso que deixa a música única. Pense em: onde se conheceram, uma mania {dela}, "
                 "uma frase que {ela} sempre fala, algo que vocês viveram juntos.",
        "exemplo": "Ex.: Todo domingo fazia bolo de fubá. Cantava hinos lavando a louça. "
                   "Criou 4 filhos sozinha trabalhando de costureira.",
        "obrigatoria": True,
    },
    {
        "chave": "frase_obrigatoria", "tipo": "texto",
        "titulo": "Tem alguma frase que não pode faltar na música de {nome}?",
        "exemplo": "Ex.: Deus é fiel (pode deixar em branco)",
    },
    {
        "chave": "clima", "tipo": "opcoes",
        "titulo": "Como você quer que {nome} se sinta ouvindo?",
        "opcoes": [["emocionante", "Emocionado 🥹"], ["alegre", "Alegre 😄"], ["engracado", "Rindo 😂"]],
    },
    {
        "chave": "estilo", "tipo": "opcoes",
        "titulo": "Qual estilo {nome} mais gosta?",
        "opcoes": [["sertanejo", "Sertanejo romântico"], ["sertanejo_universitario", "Sertanejo universitário"],
                   ["sertanejo_raiz", "Modão / Sertanejo raiz"], ["gospel", "Gospel"],
                   ["pagode", "Pagode"], ["samba", "Samba"], ["forro", "Forró"], ["piseiro", "Piseiro"],
                   ["arrocha", "Arrocha"], ["mpb", "MPB"], ["pop", "Pop"], ["romantica", "Romântica"],
                   ["bossa", "Bossa nova"], ["rock", "Rock"], ["axe", "Axé"], ["funk", "Funk"],
                   ["reggae", "Reggae"], ["rap", "Rap / Hip-hop"], ["valsa", "Valsa"], ["infantil", "Infantil"]],
    },
    {
        "chave": "voz", "tipo": "opcoes",
        "titulo": "Quem vai cantar pra {nome}?",
        "opcoes": [["feminina", "Voz feminina"], ["masculina", "Voz masculina"], ["dupla", "Dupla sertaneja"]],
    },
    {
        "chave": "de", "tipo": "texto",
        "titulo": "E o seu nome?",
        "ajuda": "Vai na dedicatória da música pra {nome} 💛",
        "exemplo": "Ex.: Patrícia",
        "obrigatoria": True,
    },
    {
        "chave": "contato", "tipo": "contato",
        "titulo": "{de}, pra onde mandamos a música de {nome}?",
        "ajuda": "Avisamos assim que ela ficar pronta.",
    },
]

CHAVES_VALIDAS = {p["chave"] for p in PERGUNTAS} - {"contato"}

# Para trocar {da_sua_pessoa}, {ela} e {dela} conforme a resposta de "Pra quem é a música?".
FEMININO = {"Mãe", "Esposa", "Namorada", "Filha", "Irmã", "Avó", "Amiga"}
MASCULINO = {"Pai", "Marido", "Namorado", "Filho", "Irmão", "Avô", "Amigo"}
