(() => {
  const root = document.querySelector("[data-carousel]");
  if (!root) return;

  const track = root.querySelector("[data-carousel-track]");
  const slides = [...root.querySelectorAll("[data-carousel-slide]")];
  const dotsWrap = root.querySelector("[data-carousel-dots]");
  const prevBtn = root.querySelector("[data-carousel-prev]");
  const nextBtn = root.querySelector("[data-carousel-next]");
  if (!track || slides.length === 0) return;

  let index = 0;
  let timer = null;
  const AUTO_MS = 4500;

  const dots = slides.map((_, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-label", `Show screenshot ${i + 1}`);
    btn.addEventListener("click", () => goTo(i, true));
    dotsWrap?.appendChild(btn);
    return btn;
  });

  function goTo(next, user = false) {
    index = (next + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      slide.classList.toggle("is-active", i === index);
    });
    dots.forEach((dot, i) => {
      dot.setAttribute("aria-selected", i === index ? "true" : "false");
    });
    centerActive();
    if (user) restartAuto();
  }

  function centerActive() {
    const active = slides[index];
    const viewport = track.parentElement;
    if (!active || !viewport) return;
    const viewportCenter = viewport.clientWidth / 2;
    const slideCenter = active.offsetLeft + active.offsetWidth / 2;
    const x = viewportCenter - slideCenter;
    track.style.transform = `translateX(${x}px)`;
  }

  function restartAuto() {
    clearInterval(timer);
    timer = setInterval(() => goTo(index + 1), AUTO_MS);
  }

  prevBtn?.addEventListener("click", () => goTo(index - 1, true));
  nextBtn?.addEventListener("click", () => goTo(index + 1, true));

  let touchX = null;
  track.addEventListener(
    "touchstart",
    (e) => {
      touchX = e.changedTouches[0]?.clientX ?? null;
    },
    { passive: true },
  );
  track.addEventListener(
    "touchend",
    (e) => {
      if (touchX == null) return;
      const dx = (e.changedTouches[0]?.clientX ?? touchX) - touchX;
      if (Math.abs(dx) > 40) goTo(index + (dx < 0 ? 1 : -1), true);
      touchX = null;
    },
    { passive: true },
  );

  window.addEventListener("resize", () => centerActive());

  // Wait for images so offsetLeft is accurate
  const imgs = [...track.querySelectorAll("img")];
  Promise.all(
    imgs.map(
      (img) =>
        img.complete
          ? Promise.resolve()
          : new Promise((resolve) => {
              img.addEventListener("load", resolve, { once: true });
              img.addEventListener("error", resolve, { once: true });
            }),
    ),
  ).then(() => {
    goTo(0);
    restartAuto();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearInterval(timer);
    else restartAuto();
  });
})();
