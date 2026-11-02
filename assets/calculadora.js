// Calculadora y carrito guiado de Kit72. La lógica de cantidades es la misma que
// calcular() en scripts/generar_sitio.py (mantenerlas iguales).
// Si Mercado Libre regresa aquí después de autorizar la app, muestra el código para copiarlo.
(function () {
  let codigo = null;
  try { codigo = new URLSearchParams(location.search).get("code"); } catch (e) { return; }
  if (!codigo || !/^TG-/.test(codigo)) return;
  const caja = document.createElement("div");
  caja.className = "aviso-codigo";
  caja.innerHTML = '<strong>Autorización recibida.</strong> Copia este código y pégalo en GitHub en los próximos minutos ' +
    '(Actions → Actualizar precios y publicar → Run workflow → campo del código):' +
    '<code id="codigo-ml"></code><button type="button" class="btn" id="copiar-codigo">Copiar código</button>';
  document.body.prepend(caja);
  document.getElementById("codigo-ml").textContent = codigo;
  document.getElementById("copiar-codigo").addEventListener("click", function () {
    try { navigator.clipboard.writeText(codigo); this.textContent = "Copiado ✓"; } catch (e) { /* copia manual */ }
  });
  try { history.replaceState(null, "", location.pathname); } catch (e) { /* sin cambios */ }
})();

(function () {
  const D = window.KIT72;
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => D.simbolo + Math.round(n).toLocaleString("es-MX");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const CLAVE = "kit72-agregados";
  let kit = "maximo";
  let agregados = {};

  // Preferencias del visitante en su navegador (opcional; el sitio funciona sin ellas)
  function leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE)) || {}; } catch (e) { return {}; }
  }
  function guardar() {
    try { localStorage.setItem(CLAVE, JSON.stringify(agregados)); } catch (e) { /* sin almacenamiento */ }
  }

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

  function progreso(filas) {
    const enLinea = filas.filter((f) => !f.local);
    const hechos = enLinea.filter((f) => agregados[f.id]).length;
    $("progreso-txt").textContent = `${hechos} de ${enLinea.length} agregados`;
    $("barra").style.width = enLinea.length ? `${(hechos / enLinea.length) * 100}%` : "0";
    $("ir-carrito").classList.toggle("listo", hechos === enLinea.length && hechos > 0);
  }

  function pintar() {
    const adultos = Math.max(1, Math.min(12, parseInt($("adultos").value, 10) || 1));
    const ninos = Math.max(0, Math.min(12, parseInt($("ninos").value, 10) || 0));
    const { filas, total } = calcular(kit, adultos, ninos);
    $("desc-kit").textContent = D.kits[kit].descripcion;
    const lista = (D.listas || {})[kit];
    $("lista-completa").innerHTML = lista
      ? `<p><a class="btn-sec" rel="sponsored nofollow noopener" target="_blank" href="${esc(lista)}">Ver el kit ${esc(D.kits[kit].nombre)} completo en Mercado Libre</a></p>`
      : "";
    let html = "";
    for (const cat of D.categorias) {
      const g = filas.filter((f) => f.categoria === cat);
      if (!g.length) continue;
      html += `<h3 class="cat">${esc(cat)}</h3><ul class="lista">`;
      for (const f of g) {
        const nota = f.nota ? `<small>${esc(f.nota)}</small>` : "";
        const agotado = f.disponible === false ? ' <span class="agotado">Agotado, lo estamos reemplazando</span>' : "";
        if (f.local) {
          html += `<li><div><strong>${esc(f.nombre)}</strong>${nota}</div>` +
            `<div class="cant">${Math.round(f.unidades * 10) / 10} ${esc(f.unidad)}</div>` +
            `<span class="local">Cómpralo en ${esc(f.lugar)}</span></li>`;
          continue;
        }
        const hecho = !!agregados[f.id];
        const cantidad = f.paquetes > 1 ? `<span class="pide">Pide ${f.paquetes} piezas</span>` : "";
        html += `<li class="${hecho ? "hecho" : ""}"><div><strong>${esc(f.nombre)}</strong>${agotado}${cantidad}${nota}</div>` +
          `<div class="cant">${f.paquetes} paq. · ${fmt(f.subtotal)}</div>` +
          `<a class="btn${hecho ? " btn-hecho" : ""}" data-id="${esc(f.id)}" rel="sponsored nofollow noopener" target="_blank" href="${esc(f.liga)}">${hecho ? "✓ Agregado" : "Agregar"}</a></li>`;
      }
      html += "</ul>";
    }
    $("resultado").innerHTML = html;
    $("total").textContent = fmt(total);
    progreso(filas);
  }

  // Al tocar "Agregar" se abre Mercado Libre en otra pestaña y el producto queda marcado
  $("resultado").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-id]");
    if (!a) return;
    const id = a.dataset.id;
    if (agregados[id] && !confirm("¿Quitar la marca de agregado a este producto?")) {
      e.preventDefault();
      return;
    }
    if (agregados[id]) {
      e.preventDefault();
      delete agregados[id];
    } else {
      agregados[id] = true;
    }
    guardar();
    setTimeout(pintar, 50);
  });

  $("reiniciar").addEventListener("click", () => {
    agregados = {};
    guardar();
    pintar();
  });

  document.querySelectorAll(".pestanas button").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".pestanas button").forEach((x) => x.classList.remove("activo"));
      b.classList.add("activo");
      kit = b.dataset.kit;
      pintar();
    });
  });
  ["adultos", "ninos"].forEach((id) => $(id).addEventListener("input", pintar));

  agregados = leer();
  pintar();
})();
