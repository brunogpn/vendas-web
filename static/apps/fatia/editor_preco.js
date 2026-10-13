/*
  Formulário de preço de um ingrediente ("Meus preços" e direto na calculadora).
  EditorPreco.abrir(container, itemId, precoAtual, aoTerminar) — aoTerminar(novoPreco | null).
  Depende de App (app.js) e Custos (custos.js, já iniciado com o catálogo).
*/
(function () {
  'use strict';
  var UNIDADE = { g: 'gramas', ml: 'ml', un: 'unidades' };

  function abrir(container, item, atual, aoTerminar) {
    var ing = Custos.ingrediente(item);
    var dica = 'O mais comum é ' + ing.rotuloEmbalagem + '.' +
      (ing.unidade === 'g' && ing.embalagem >= 1000 ? ' 1 kg = 1000 gramas.' : '') +
      (ing.unidade === 'ml' && ing.embalagem >= 900 ? ' 1 litro = 1000 ml.' : '');
    container.innerHTML =
      '<form class="surgir pilha" style="padding-top:4px" novalidate>' +
        '<div class="grade-2">' +
          '<label><span class="rotulo">Preço</span><span class="campo-reais" style="display:block"><span>R$</span>' +
            '<input class="campo numeros negrito" data-preco inputmode="decimal" placeholder="0,00" value="' + App.paraCampo(atual && atual.preco) + '"></span></label>' +
          '<label><span class="rotulo">Embalagem</span><span class="campo-sufixo" style="display:block">' +
            '<input class="campo numeros negrito" style="padding-right:90px" data-tamanho inputmode="decimal" value="' +
            App.paraCampo(atual ? atual.quantidade : ing.embalagem) + '"><span class="pequeno">' + UNIDADE[ing.unidade] + '</span></span></label>' +
        '</div>' +
        '<p class="suave pequeno">' + App.escapar(dica) + '</p>' +
        '<p class="erro" role="alert" hidden data-erro></p>' +
        '<button type="submit" class="botao" data-salvar>' + App.icone('Check') + ' Salvar preço</button>' +
        (atual ? '<button type="button" class="botao-texto" style="width:100%;justify-content:center" data-apagar>Apagar este preço</button>' : '') +
      '</form>';
    var form = container.querySelector('form');
    var erro = form.querySelector('[data-erro]');
    var campoPreco = form.querySelector('[data-preco]');
    setTimeout(function () { campoPreco.focus(); }, 50);
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      App.mostrarErro(erro, '');
      var p = { item: item, preco: App.lerNumero(campoPreco.value), quantidade: App.lerNumero(form.querySelector('[data-tamanho]').value) };
      App.ocupado(form.querySelector('[data-salvar]'), 'Salvando...', App.post(APP.prefixo + '/precos/salvar', p)).then(function (r) {
        if (!r.ok) return App.mostrarErro(erro, r.erro);
        aoTerminar(r.preco);
      });
    });
    var apagar = form.querySelector('[data-apagar]');
    if (apagar) apagar.addEventListener('click', function () {
      App.ocupado(apagar, 'Apagando...', App.post(APP.prefixo + '/precos/apagar', { item: item })).then(function (r) {
        if (!r.ok) return App.mostrarErro(erro, r.erro);
        aoTerminar(null);
      });
    });
  }

  window.EditorPreco = { abrir: abrir };
})();
