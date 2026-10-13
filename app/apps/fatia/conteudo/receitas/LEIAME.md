# Formato dos arquivos de receita

Cada `.txt` desta pasta vira `src/conteudo/receitas.json` com `npm run receitas` (roda sozinho antes do `dev` e do `build`). O script avisa e para se encontrar algo errado.

```
@ id-da-receita | Nome da Receita | categoria | página do PDF
desc: Frase curta sobre a receita.
rend: Texto do rendimento.
fatias: 16              ← número usado na calculadora (fatias ou unidades)
un: brigadeiros         ← unidade, quando não é fatia
val: Validade.
dif: fácil | média | difícil
selos: Selo 1; Selo 2
usa: id-de-outra-receita, outro-id
obs: Observação do app (pode repetir). Aparece num quadro à parte.
dica: Dica.
combina: Com o que combina.
## Grupo de ingredientes
- 3 ovos [ovo 3]                ← [ingrediente quantidade] entra no custo e na lista de compras
- Chantininho [~chantilly 200]  ← ~ marca quantidade estimada
- Calda de baunilha {calda-baunilha}   ← {id} mostra o atalho "Ver receita"
### Grupo do modo de preparo
* Passo.
> Tradicional: versão da fatia
```

Categorias: `fatias` e `brigadeiros` aparecem na lista de Receitas. As bases (`massas`, `caldas`, `recheios`, `geleias`, `coberturas`) não aparecem na lista: abrem a partir das fatias que as citam.

Os ingredientes de `[ingrediente quantidade]` precisam existir em `src/conteudo/ingredientes.ts`.
