/*
  JS base dos apps das clientes (/app/<slug>/). Sem framework: cada tela usa estas funções.
  O template base define window.APP = { prefixo, icones, som } antes de carregar este arquivo.
*/
(function () {
  'use strict';
  var APP = window.APP || {};

  // ---------- formato (mesmas regras de apps/_nucleo/formato.py) ----------
  var fmt2 = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  var fmt0 = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  function reais(v) { return fmt2.format(v || 0); }
  function reaisSemCentavos(v) { return fmt0.format(v || 0); }
  var MILHAR = /^-?\d{1,3}(\.\d{3})+$/;
  // Lê o que a cliente digitou: "12,50", "12.50", "R$ 1.234,56", "1.000" (= mil).
  function lerNumero(texto) {
    if (texto == null) return 0;
    var limpo = String(texto).replace(/[^\d,.-]/g, '');
    var normal = limpo.indexOf(',') >= 0 ? limpo.replace(/\./g, '').replace(',', '.')
      : (MILHAR.test(limpo) ? limpo.replace(/\./g, '') : limpo);
    var n = Number(normal);
    return isFinite(n) ? n : 0;
  }
  // Número para mostrar num campo: 0 → "", 12.5 → "12,5".
  function paraCampo(n) { return !n ? '' : String(Math.round(n * 100) / 100).replace('.', ','); }
  function semAcento(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim(); }
  function plural(n, um, varios) { return n === 1 ? um : varios; }

  // ---------- ícones ----------
  function icone(nome, classe, preenchido) {
    return '<svg class="ic ' + (classe || '') + '" aria-hidden="true"><use href="' + APP.icones + '#' + nome +
      (preenchido ? '-fill' : '') + '"></use></svg>';
  }
  function escapar(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ---------- servidor ----------
  // POST JSON para uma ação do app. Devolve sempre um objeto {ok, erro?, ...} (nunca lança).
  function post(caminho, dados) {
    return fetch(caminho.charAt(0) === '/' ? caminho : APP.prefixo + '/' + caminho, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(dados || {})
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, erro: 'Algo deu errado. Tente de novo.' }; })
        .then(function (j) {
          if (j && j.entrar) { window.location.href = APP.prefixo + '/entrar'; }
          return j || { ok: false, erro: 'Algo deu errado. Tente de novo.' };
        });
    }).catch(function () {
      return { ok: false, erro: 'Sem conexão com a internet. Confira e tente de novo.' };
    });
  }

  // Botão ocupado: troca o texto e desabilita enquanto a promessa não termina.
  function ocupado(botao, textoOcupado, promessa) {
    var original = botao.innerHTML;
    botao.disabled = true;
    botao.textContent = textoOcupado;
    return promessa.then(function (r) { botao.disabled = false; botao.innerHTML = original; return r; },
      function (e) { botao.disabled = false; botao.innerHTML = original; throw e; });
  }

  function mostrarErro(el, msg) {
    if (!el) return;
    el.textContent = msg || '';
    el.hidden = !msg;
  }

  // ---------- guardado só neste aparelho (localStorage) ----------
  function ler(chave, inicial) {
    try { var v = localStorage.getItem(chave); return v == null ? inicial : JSON.parse(v); } catch (e) { return inicial; }
  }
  function gravar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); } catch (e) { /* aba anônima ou cheia: ignora */ }
  }

  // Itens marcáveis guardados no aparelho: <ul data-marcaveis="chave"> com botões .marcavel[data-id].
  function iniciarMarcaveis(raiz) {
    (raiz || document).querySelectorAll('[data-marcaveis]').forEach(function (lista) {
      var chave = lista.getAttribute('data-marcaveis');
      var marcados = ler(chave, []);
      var limpar = document.querySelector('[data-limpar-marcaveis="' + chave + '"]');
      function atualizar() {
        lista.querySelectorAll('.marcavel').forEach(function (b) {
          b.setAttribute('aria-checked', marcados.indexOf(b.getAttribute('data-id')) >= 0 ? 'true' : 'false');
        });
        if (limpar) limpar.hidden = marcados.length === 0;
      }
      lista.addEventListener('click', function (ev) {
        var b = ev.target.closest('.marcavel');
        if (!b) return;
        var id = b.getAttribute('data-id');
        var i = marcados.indexOf(id);
        if (i >= 0) marcados.splice(i, 1); else marcados.push(id);
        gravar(chave, marcados);
        atualizar();
      });
      if (limpar) limpar.addEventListener('click', function () { marcados = []; gravar(chave, marcados); atualizar(); });
      atualizar();
    });
  }

  // ---------- comemoração: painel que sobe, confete e o "plim" ----------
  var CORES = ['#c4402a', '#1f7a4d', '#1e1e1c', '#e4e2dd'];
  var poucoMovimento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function confete(forte) {
    if (poucoMovimento || typeof window.confetti !== 'function') return;
    if (forte) {
      window.confetti({ particleCount: 140, spread: 100, origin: { y: 0.55 }, colors: CORES });
      setTimeout(function () { window.confetti({ particleCount: 90, spread: 120, origin: { y: 0.35 }, colors: CORES }); }, 400);
    } else {
      window.confetti({ particleCount: 70, spread: 70, origin: { y: 0.55 }, colors: CORES });
    }
  }

  // Três notas curtas (mi, lá, mi agudo), geradas no navegador: não precisa de arquivo de som.
  function plim() {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      var ctx = new Ctx();
      [659.25, 880, 1318.5].forEach(function (freq, i) {
        var t = ctx.currentTime + i * 0.11;
        var osc = ctx.createOscillator();
        var vol = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        vol.gain.setValueAtTime(0.0001, t);
        vol.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
        vol.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
        osc.connect(vol).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.4);
      });
    } catch (e) { /* sem som, sem problema */ }
  }

  // opcoes: { titulo, mensagem, conquistas: {pontosGanhos, subiuNivel, novasMedalhas}, botao, onFechar }
  function comemorar(opcoes) {
    var c = opcoes.conquistas || {};
    var medalhas = c.novasMedalhas || [];
    var forte = !!c.subiuNivel || medalhas.length > 0;
    var itens = '';
    var atraso = 360;
    if (c.subiuNivel) {
      itens += '<li class="linha surgir" style="--atraso:' + atraso + 'ms"><span class="selo selo-tomate" style="width:44px;height:44px">' +
        icone(c.subiuNivel.icone, '', true) + '</span><div><p class="suave pequeno">Você subiu de nível</p><p class="negrito">' +
        escapar(c.subiuNivel.nome) + '</p></div></li>';
      atraso = 420;
    }
    medalhas.forEach(function (m, i) {
      itens += '<li class="linha surgir" style="--atraso:' + (420 + i * 60) + 'ms"><span class="selo selo-tinta" style="width:44px;height:44px">' +
        icone(m.icone, '', true) + '</span><div><p class="suave pequeno">Medalha nova</p><p class="negrito">' +
        escapar(m.nome) + '</p></div></li>';
    });
    var raiz = document.createElement('div');
    raiz.className = 'painel-raiz';
    raiz.setAttribute('data-aberto', 'false');
    raiz.innerHTML =
      '<div class="painel-fundo" data-fechar></div>' +
      '<div class="painel centro" role="dialog" aria-modal="true" aria-labelledby="comemoracao-titulo">' +
        '<span class="selo selo-verde estourar" style="--atraso:180ms;width:72px;height:72px">' + icone('Check', 'ic-lg') + '</span>' +
        '<h2 id="comemoracao-titulo" class="mt-4" style="font-size:1.75rem">' + escapar(opcoes.titulo) + '</h2>' +
        (c.pontosGanhos > 0 ? '<p class="verde-txt negrito mt-1">+' + c.pontosGanhos + ' pontos</p>' : '') +
        (opcoes.mensagem ? '<p class="suave mt-2">' + escapar(opcoes.mensagem) + '</p>' : '') +
        (itens ? '<ul class="caixa-areia mt-4 pilha" style="text-align:left;--gap:12px">' + itens + '</ul>' : '') +
        '<button type="button" class="botao mt-6" data-fechar-botao>' + escapar(opcoes.botao || 'Continuar') + '</button>' +
      '</div>';
    document.body.appendChild(raiz);
    var botao = raiz.querySelector('[data-fechar-botao]');
    requestAnimationFrame(function () { requestAnimationFrame(function () { raiz.setAttribute('data-aberto', 'true'); botao.focus(); }); });
    confete(forte);
    if (APP.som) plim();
    var fechando = false;
    function fechar() {
      if (fechando) return;
      fechando = true;
      raiz.setAttribute('data-aberto', 'false');
      document.removeEventListener('keydown', tecla);
      setTimeout(function () { raiz.remove(); if (opcoes.onFechar) opcoes.onFechar(); }, poucoMovimento ? 250 : 500);
    }
    function tecla(ev) { if (ev.key === 'Escape') fechar(); }
    botao.addEventListener('click', fechar);
    raiz.querySelector('[data-fechar]').addEventListener('click', fechar);
    document.addEventListener('keydown', tecla);
  }

  // ---------- botões comuns ----------
  function iniciarCopiar(raiz) {
    (raiz || document).querySelectorAll('[data-copiar]').forEach(function (b) {
      b.addEventListener('click', function () {
        var alvo = document.getElementById(b.getAttribute('data-copiar'));
        var texto = alvo ? alvo.innerText : '';
        var ok = function () {
          var original = b.innerHTML;
          b.innerHTML = icone('Check') + ' Copiado. Agora é só colar';
          b.classList.add('copiado');
          b.style.background = 'var(--verde-claro)';
          setTimeout(function () { b.innerHTML = original; b.style.background = ''; }, 2500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(ok, function () {});
        else {
          var t = document.createElement('textarea'); t.value = texto; document.body.appendChild(t); t.select();
          try { document.execCommand('copy'); ok(); } catch (e) { /* nada */ }
          t.remove();
        }
      });
    });
  }

  // Voltar pelo histórico quando veio de dentro do app (senão, vai para o href).
  function iniciarVoltarAnterior() {
    document.querySelectorAll('[data-voltar-anterior]').forEach(function (a) {
      a.addEventListener('click', function (ev) {
        if (window.history.length > 1 && document.referrer && new URL(document.referrer).origin === location.origin) {
          ev.preventDefault();
          window.history.back();
        }
      });
    });
  }

  // Sair do app.
  function iniciarSair() {
    document.querySelectorAll('[data-sair]').forEach(function (b) {
      b.addEventListener('click', function () {
        post(APP.prefixo + '/sair', {}).then(function (r) { window.location.href = (r && r.destino) || APP.prefixo + '/entrar'; });
      });
    });
  }

  // Service worker: só para o navegador oferecer "instalar" (sem cache offline).
  if ('serviceWorker' in navigator && APP.prefixo) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(APP.prefixo + '/sw.js', { scope: APP.prefixo + '/' }).catch(function () {});
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    iniciarMarcaveis();
    iniciarCopiar();
    iniciarVoltarAnterior();
    iniciarSair();
  });

  window.App = {
    reais: reais, reaisSemCentavos: reaisSemCentavos, lerNumero: lerNumero, paraCampo: paraCampo,
    semAcento: semAcento, plural: plural, icone: icone, escapar: escapar,
    post: post, ocupado: ocupado, mostrarErro: mostrarErro, ler: ler, gravar: gravar,
    iniciarMarcaveis: iniciarMarcaveis, comemorar: comemorar, confete: confete, plim: plim
  };
})();
