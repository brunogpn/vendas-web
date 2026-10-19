// Player de áudio do site. Uso: <div class="player" data-src="/arquivo.mp3" data-titulo="Versão 1"></div>
// Toca um de cada vez; chame Player.montar(elementoPai) depois de inserir players novos na página.
(function () {
  const audio = new Audio();
  audio.preload = "none";
  let atual = null;

  const tempo = s => (isFinite(s) ? Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0") : "0:00");

  function parar() {
    if (!atual) return;
    atual.classList.remove("tocando");
    atual.querySelector(".player-botao").innerHTML = '<i class="ti ti-player-play" aria-hidden="true"></i>';
    atual.querySelector(".player-botao").setAttribute("aria-label", "Tocar");
    atual = null;
  }

  function montarUm(el) {
    if (el.dataset.montado) return;
    el.dataset.montado = "1";
    el.innerHTML =
      '<button class="player-botao" type="button" aria-label="Tocar"><i class="ti ti-player-play" aria-hidden="true"></i></button>' +
      '<div class="player-corpo">' +
      (el.dataset.titulo ? '<span class="player-titulo"></span>' : "") +
      '<div class="player-barra" role="slider" aria-label="Posição da música" tabindex="0"><div class="player-cheio"></div></div>' +
      '<div class="player-tempos"><span class="player-agora">0:00</span><span class="player-total">' + (el.dataset.duracao || "") + "</span></div>" +
      "</div>";
    if (el.dataset.titulo) el.querySelector(".player-titulo").textContent = el.dataset.titulo;

    el.querySelector(".player-botao").addEventListener("click", () => {
      if (atual === el) {
        if (audio.paused) { audio.play(); } else { audio.pause(); }
        return;
      }
      parar();
      atual = el;
      audio.src = el.dataset.src;
      audio.play();
    });

    const barra = el.querySelector(".player-barra");
    const pular = x => {
      if (atual !== el || !audio.duration) return;
      const r = barra.getBoundingClientRect();
      audio.currentTime = Math.max(0, Math.min(1, (x - r.left) / r.width)) * audio.duration;
    };
    barra.addEventListener("click", e => pular(e.clientX));
    barra.addEventListener("keydown", e => {
      if (atual !== el) return;
      if (e.key === "ArrowRight") audio.currentTime += 5;
      if (e.key === "ArrowLeft") audio.currentTime -= 5;
    });
  }

  audio.addEventListener("play", () => {
    if (!atual) return;
    atual.classList.add("tocando");
    const b = atual.querySelector(".player-botao");
    b.innerHTML = '<i class="ti ti-player-pause" aria-hidden="true"></i>';
    b.setAttribute("aria-label", "Pausar");
  });
  audio.addEventListener("pause", () => {
    if (!atual) return;
    const b = atual.querySelector(".player-botao");
    b.innerHTML = '<i class="ti ti-player-play" aria-hidden="true"></i>';
    b.setAttribute("aria-label", "Tocar");
  });
  audio.addEventListener("timeupdate", () => {
    if (!atual) return;
    const p = audio.duration ? (audio.currentTime / audio.duration) * 100 : 0;
    atual.querySelector(".player-cheio").style.width = p + "%";
    atual.querySelector(".player-agora").textContent = tempo(audio.currentTime);
    atual.querySelector(".player-total").textContent = tempo(audio.duration);
  });
  audio.addEventListener("ended", () => {
    if (atual) atual.querySelector(".player-cheio").style.width = "0%";
    parar();
  });

  window.Player = {
    montar(raiz) { (raiz || document).querySelectorAll(".player").forEach(montarUm); },
    parar() { audio.pause(); parar(); },
  };
  document.addEventListener("DOMContentLoaded", () => window.Player.montar());
})();
