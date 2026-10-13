/*
  Seletor de receita de venda (calculadora e lista de compras): busca sem acento, botões
  Fatias/Brigadeiros (somem quando há busca) e lista com miniatura.
  EscolherReceita.montar(container, receitas, { marcadas: [ids], aoEscolher: fn(id), static: '/static/...' })
*/
(function () {
  'use strict';

  function montar(container, receitas, opcoes) {
    var categoria = 'fatias';
    var marcadas = opcoes.marcadas || [];
    container.innerHTML =
      '<div style="position:relative"><span style="position:absolute;left:16px;top:50%;transform:translateY(-50%);color:var(--suave)">' +
        App.icone('MagnifyingGlass') + '</span><input class="campo" style="padding-left:48px" type="search" placeholder="Buscar pelo nome" ' +
        'aria-label="Buscar receita" autocomplete="off" data-busca></div>' +
      '<div class="grade-2 mt-3" data-categorias>' +
        '<button type="button" class="opcao" data-categoria="fatias">Fatias</button>' +
        '<button type="button" class="opcao" data-categoria="brigadeiros">Brigadeiros</button></div>' +
      '<ul class="cartao lista-linhas mt-3" style="padding:0;overflow:hidden" data-lista></ul>' +
      '<p class="suave mt-3" data-vazio hidden>Nenhuma receita com esse nome.</p>';
    var busca = container.querySelector('[data-busca]');
    var cats = container.querySelector('[data-categorias]');
    var lista = container.querySelector('[data-lista]');

    function desenhar() {
      var termo = App.semAcento(busca.value);
      cats.hidden = !!termo;
      cats.querySelectorAll('.opcao').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-categoria') === categoria ? 'true' : 'false'); });
      var vis = receitas.filter(function (r) { return termo ? r.busca.indexOf(termo) >= 0 : r.categoria === categoria; });
      lista.hidden = vis.length === 0;
      container.querySelector('[data-vazio]').hidden = vis.length > 0;
      lista.innerHTML = vis.map(function (r) {
        var foto = r.imagem ? '<img src="' + opcoes.static + r.imagem + '" alt="" loading="lazy" style="width:56px;height:56px;border-radius:12px;object-fit:cover">'
          : '<span style="width:56px;height:56px;border-radius:12px;background:var(--areia);display:inline-flex;align-items:center;justify-content:center;color:var(--suave)">' +
            App.icone(r.categoria === 'brigadeiros' ? 'Cookie' : 'Cake') + '</span>';
        var fim = marcadas.indexOf(r.id) >= 0 ? '<span class="verde-txt pequeno negrito">' + App.icone('Check', 'ic-sm') + ' Na lista</span>' : '<span class="suave">›</span>';
        return '<li><button type="button" class="item-nav" style="width:100%;text-align:left;min-height:64px" data-id="' + r.id + '">' + foto +
          '<span class="cresce negrito">' + App.escapar(r.nome) + '</span>' + fim + '</button></li>';
      }).join('');
    }
    busca.addEventListener('input', desenhar);
    cats.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-categoria]'); if (!b) return;
      categoria = b.getAttribute('data-categoria');
      desenhar();
    });
    lista.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-id]'); if (!b) return;
      opcoes.aoEscolher(b.getAttribute('data-id'));
    });
    desenhar();
  }

  window.EscolherReceita = { montar: montar };
})();
