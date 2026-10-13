/*
  Contas de custo e de compras do App Fatias (calculadora e lista de compras). Rodam no celular,
  ao vivo enquanto a cliente digita. Porte do src/lib/custos.ts do projeto do Bruno — mesmas regras.
  Uso: Custos.iniciar(catalogoDeIngredientes) antes de chamar as outras funções.
*/
(function () {
  'use strict';
  var ING = {};

  // Gás, luz e o que se perde na produção, sobre o custo dos ingredientes.
  var RESERVA_GAS_LUZ = 0.1;

  // Preços sugeridos: o maior entre "vezes o custo" e o preço mínimo de mercado (uma fatia barata de
  // fazer não sai vendida abaixo do que se cobra na feira). Fatias: começa em R$ 18. Brigadeiros:
  // faixas do ebook (tradicional, gourmet, premium).
  var FAIXAS = {
    fatias: [{ minimo: 18, vezes: 4 }, { minimo: 22, vezes: 5 }, { minimo: 26, vezes: 6 }],
    brigadeiros: [{ minimo: 3, vezes: 2 }, { minimo: 5, vezes: 2.5 }, { minimo: 8, vezes: 3 }]
  };
  var TEXTOS = [
    { id: 'comecar', nome: 'Para começar', texto: 'O preço de entrada na feira, sem desvalorizar seu trabalho.' },
    { id: 'recomendado', nome: 'Recomendado', texto: 'Cobre seus gastos e deixa um ótimo lucro.' },
    { id: 'especial', nome: 'Especial', texto: 'Para sabores caprichados, com Nutella, pistache ou frutas.' }
  ];

  function iniciar(catalogo) {
    ING = {};
    catalogo.forEach(function (i) { ING[i.id] = i; });
  }

  function sugestoesDePreco(categoria, custo) {
    var faixas = FAIXAS[categoria] || FAIXAS.fatias;
    // Fatia em reais inteiros (fácil de dar troco); brigadeiro de 50 em 50 centavos.
    var passo = categoria === 'brigadeiros' ? 0.5 : 1;
    return faixas.map(function (f, i) {
      return Object.assign({}, TEXTOS[i], { preco: Math.max(f.minimo, Math.ceil((custo * f.vezes) / passo - 1e-9) * passo) });
    });
  }

  function nomeUnidade(r, n) {
    var singular = r.categoria === 'brigadeiros' ? 'brigadeiro' : 'fatia';
    return n === 1 ? singular : singular + 's';
  }

  function tamanhoEmbalagem(item, precos) {
    return (precos[item] && precos[item].quantidade) || (ING[item] && ING[item].embalagem) || 1;
  }

  function custoDeItens(itens, precos) {
    var total = 0, semPreco = [];
    itens.forEach(function (it) {
      var p = precos[it.item];
      if (!p || !p.quantidade) semPreco.push(it.item);
      else total += (p.preco / p.quantidade) * it.qtd;
    });
    return { total: total, semPreco: semPreco };
  }

  // Soma os ingredientes de várias receitas (cada uma feita "vezes" vezes).
  function somarItens(escolha) {
    var soma = {}, ordem = [], outros = [];
    escolha.forEach(function (e) {
      e.receita.itens.forEach(function (it) {
        if (!(it.item in soma)) { soma[it.item] = 0; ordem.push(it.item); }
        soma[it.item] += it.qtd * e.vezes;
      });
      e.receita.outros.forEach(function (o) { if (outros.indexOf(o) < 0) outros.push(o); });
    });
    return { itens: ordem.map(function (k) { return { item: k, qtd: soma[k] }; }), outros: outros };
  }

  // "pacote de 1 kg" → "pacotes de 1 kg"; "lata ou caixa de 395 g" → "latas ou caixas de 395 g".
  function plural(rotulo) {
    var semParenteses = rotulo.replace(/\s*\(.*\)$/, '');
    var m = semParenteses.match(/^(.*?) ((?:de |com ).*)$/);
    var antes = m ? m[1] : semParenteses;
    var resto = m ? ' ' + m[2] : '';
    var palavras = antes.split(' ').map(function (p) {
      return p === 'ou' ? p : (/ão$/.test(p) ? p.slice(0, -2) + 'ões' : p + 's');
    });
    return palavras.join(' ') + resto;
  }

  var fmtKg = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
  function textoQuantidade(qtd, unidade) {
    if (unidade === 'un') {
      var n = Math.ceil(qtd * 10) / 10;
      return String(n).replace('.', ',') + ' ' + (n === 1 ? 'unidade' : 'unidades');
    }
    if (qtd >= 1000) return fmtKg.format(qtd / 1000) + ' ' + (unidade === 'g' ? 'kg' : 'litros');
    return Math.round(qtd) + ' ' + unidade;
  }

  // Quantas embalagens comprar, em texto: "2 caixinhas de 200 g", "3 unidades".
  function textoCompra(item, qtd, precos) {
    var ing = ING[item];
    var tamanho = tamanhoEmbalagem(item, precos);
    // Folga de 2% para não mandar comprar uma embalagem a mais por causa de arredondamento.
    var n = Math.max(1, Math.ceil(qtd / tamanho - 0.02));
    if (!ing) return { n: n, texto: String(n) };
    if (ing.unidade === 'un' && tamanho === 1) return { n: n, texto: n + ' ' + (n === 1 ? 'unidade' : 'unidades') };
    // Vendido a peso ("1 kg"): fala o total.
    if (tamanho === ing.embalagem && /^\d/.test(ing.rotuloEmbalagem)) return { n: n, texto: textoQuantidade(n * tamanho, ing.unidade) };
    var rotulo = tamanho === ing.embalagem ? ing.rotuloEmbalagem : 'embalagem de ' + textoQuantidade(tamanho, ing.unidade);
    return { n: n, texto: n === 1 ? '1 ' + rotulo : n + ' ' + plural(rotulo) };
  }

  function ingrediente(id) { return ING[id]; }

  window.Custos = {
    RESERVA_GAS_LUZ: RESERVA_GAS_LUZ, iniciar: iniciar, sugestoesDePreco: sugestoesDePreco, nomeUnidade: nomeUnidade,
    tamanhoEmbalagem: tamanhoEmbalagem, custoDeItens: custoDeItens, somarItens: somarItens, plural: plural,
    textoQuantidade: textoQuantidade, textoCompra: textoCompra, ingrediente: ingrediente
  };
})();
