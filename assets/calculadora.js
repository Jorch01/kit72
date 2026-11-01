// Calculadora de Kit72. Misma lógica que calcular() en scripts/generar_sitio.py
(function () {
  const D = window.KIT72;
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => D.simbolo + Math.round(n).toLocaleString("es-MX");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let kit = "maximo";

  function calcular(kit, adultos, ninos) {
    const max = D.niveles.indexOf(kit);
    const raciones = D.kits[kit].raciones || 1;
    const filas = [];
    for (const p of D.productos) {
      if (D.niveles.indexOf(p.nivel) > max) continue;
      if (p.soloNinos && ninos === 0) continue;
      const c = p.consumo || {};
      let u = (c.fijo || 0) + (c.por_adulto || 0) * adultos + (c.por_nino || 0) * ninos;
      if (p.escala) u *= raciones;
      if (u <= 0) continue;
      const paquetes = Math.ceil(u / p.rinde - 1e-9);
      filas.push({ ...p, unidades: u, paquetes, subtotal: paquetes * p.precio });
    }
    const total = filas.filter((f) => !f.local).reduce((a, f) => a + f.subtotal, 0);
    return { filas, total };
  }

  function pintar() {
    const adultos = Math.max(1, Math.min(12, parseInt($("adultos").value, 10) || 1));
    const ninos = Math.max(0, Math.min(12, parseInt($("ninos").value, 10) || 0));
    const { filas, total } = calcular(kit, adultos, ninos);
    $("desc-kit").textContent = D.kits[kit].descripcion;
    let html = "";
    for (const cat of D.categorias) {
      const g = filas.filter((f) => f.categoria === cat);
      if (!g.length) continue;
      html += `<h3 class="cat">${esc(cat)}</h3><ul class="lista">`;
      for (const f of g) {
        const nota = f.nota ? `<small>${esc(f.nota)}</small>` : "";
        const agotado = f.disponible === false ? ' <span class="agotado">Agotado, lo estamos reemplazando</span>' : "";
        const cant = f.local
          ? `${Math.round(f.unidades * 10) / 10} ${esc(f.unidad)}`
          : `${f.paquetes} paq. · ${fmt(f.subtotal)}`;
        const accion = f.local
          ? '<span class="local">Compra local</span>'
          : `<a class="btn" rel="sponsored nofollow noopener" target="_blank" href="${esc(f.liga)}">Ver en Mercado Libre</a>`;
        html += `<li><div><strong>${esc(f.nombre)}</strong>${agotado}${nota}</div><div class="cant">${cant}</div>${accion}</li>`;
      }
      html += "</ul>";
    }
    $("resultado").innerHTML = html;
    $("total").textContent = fmt(total);
  }

  document.querySelectorAll(".pestanas button").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".pestanas button").forEach((x) => x.classList.remove("activo"));
      b.classList.add("activo");
      kit = b.dataset.kit;
      pintar();
    });
  });
  ["adultos", "ninos"].forEach((id) => $(id).addEventListener("input", pintar));
  pintar();
})();
