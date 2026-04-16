document.addEventListener("DOMContentLoaded", function () {

  // Menu mobile
  var btn = document.getElementById("menuBtn");
  var nav = document.getElementById("navLinks");

  btn.addEventListener("click", function () {
    btn.classList.toggle("open");
    nav.classList.toggle("open");
  });

  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      btn.classList.remove("open");
      nav.classList.remove("open");
    });
  });

  // Scroll suave
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      var el = document.querySelector(a.getAttribute("href"));
      if (el) {
        window.scrollTo({ top: el.offsetTop - 70, behavior: "smooth" });
      }
    });
  });

  // Fade in no scroll
  var items = document.querySelectorAll(
    ".servico-card, .compliance-bloco, .compliance-topo, .pilar, .contato-info, .redes, .faixa-imagem-inner, .texto-central"
  );

  items.forEach(function (el) { el.classList.add("fade-in"); });

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  items.forEach(function (el) { observer.observe(el); });
});
