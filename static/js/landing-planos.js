/* Planos da landing (Básico + plano com o app), popup "última tentativa" e links com a campanha.
 * Usado pelas landings do Fatia em teste A/B (fatia2-e.html em /fatia-e e fatia-e.html em /fatia1-e),
 * para os dois lados se comportarem igual. Cada página passa a sua função de medição e as suas etapas.
 *
 * Marcação esperada: #checkoutBasic (obrigatório), #checkoutGuided, #checkoutGuidedDiscount,
 * #upsellOverlay com #upsellFechar e #upsellSoBasico (opcionais: só existem com o plano do app / desconto).
 *
 * ligarPlanosLanding({ track: (n, nome) => ..., etapas: { clicou, popup, recusou, aceitou, depoisPopup } })
 * cada etapa = [número, nome]. A medição guarda a etapa MAIS AVANÇADA da visita: por isso "depoisPopup"
 * (foi ao checkout depois de ver e fechar o popup) tem número maior que "popup" (viu o popup e saiu).
 */
(function () {
    // Parâmetros que pertencem ao link do checkout, não à visita: nunca copiados da URL da landing
    // (ex.: um ?plano=completo na landing não pode transformar o botão do Básico no Completo).
    var DO_CHECKOUT = { oferta: 1, plano: 1, pedido: 1, ref: 1, musica: 1 };

    // Junta a querystring da landing (gclid/campanha) com a do link, sem duplicar o "?". Sem o gclid no
    // link, a venda não volta para o Google Ads.
    function comCampanha(href) {
        var u = new URL(href, location.origin);
        new URLSearchParams(location.search).forEach(function (v, k) {
            if (!DO_CHECKOUT[k] && !u.searchParams.has(k)) u.searchParams.set(k, v);
        });
        return u.pathname + u.search;
    }

    window.ligarPlanosLanding = function (cfg) {
        var track = cfg.track, et = cfg.etapas;
        var basico = document.getElementById('checkoutBasic');
        if (!basico) return;
        var guiado = document.getElementById('checkoutGuided');
        var comDesconto = document.getElementById('checkoutGuidedDiscount');
        var overlay = document.getElementById('upsellOverlay');
        var mostrou = false;

        basico.href = comCampanha(basico.getAttribute('href'));
        if (guiado) guiado.href = comCampanha(guiado.getAttribute('href'));
        if (comDesconto) comDesconto.href = comCampanha(comDesconto.getAttribute('href'));

        var foiAoCheckout = function () { track.apply(null, mostrou ? et.depoisPopup : et.clicou); };
        var fechar = function () { overlay.classList.remove('show'); document.body.style.overflow = ''; };

        basico.addEventListener('click', function (e) {
            if (overlay && !mostrou) {  // 1º clique no Básico: oferece o plano do app com desconto
                e.preventDefault();
                mostrou = true;
                overlay.classList.add('show');
                document.body.style.overflow = 'hidden';
                track.apply(null, et.popup);
                return;
            }
            foiAoCheckout();
        });
        if (guiado) guiado.addEventListener('click', foiAoCheckout);
        if (comDesconto) comDesconto.addEventListener('click', function () { track.apply(null, et.aceitou); });
        if (!overlay) return;
        document.getElementById('upsellFechar').addEventListener('click', fechar);
        overlay.addEventListener('click', function (e) { if (e.target === overlay) fechar(); });
        window.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechar(); });
        document.getElementById('upsellSoBasico').addEventListener('click', function () {
            track.apply(null, et.recusou);
            fechar();
            window.location.href = basico.href;
        });
    };
})();
