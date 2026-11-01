#!/usr/bin/env python3
"""Genera el sitio estático de Kit72 en la carpeta _site/.

Lee config/, catalogo/ y datos/precios.json. No requiere más que PyYAML.
Uso:  python scripts/generar_sitio.py
"""
import json
import math
import shutil
import unicodedata
from datetime import date
from html import escape
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "_site"
NIVELES = ["minimo", "maximo", "plus"]
ORDEN_CATEGORIAS = ["Agua y alimentos", "Luz y comunicación", "Abrigo y seguridad",
                    "Botiquín y salud", "Higiene", "Documentos", "Kit de calma"]


def cargar(ruta):
    return yaml.safe_load((RAIZ / ruta).read_text(encoding="utf-8"))


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in t).split())


CFG = cargar("config/sitio.yaml")
CAT = cargar("catalogo/productos.yaml")["productos"]
CIUDADES = cargar("config/ciudades.yaml")["ciudades"]
RIESGOS = cargar("config/riesgos.yaml")["riesgos"]
_PRECIOS = RAIZ / "datos" / "precios.json"
PRECIOS = json.loads(_PRECIOS.read_text(encoding="utf-8")) if _PRECIOS.exists() else {}
BASE = CFG.get("ruta_base", "").rstrip("/")
URL = CFG["url_base"].rstrip("/")
HOY = date.today().isoformat()


def ruta(p=""):
    """Ruta interna respetando el subdirectorio de GitHub Pages."""
    return f"{BASE}/{p}".replace("//", "/") if p else f"{BASE}/"


def dinero(x):
    return f"{CFG.get('simbolo', '$')}{x:,.0f}"


# ---------------------------------------------------------------- datos
def producto_publico(p):
    info = PRECIOS.get(p["id"], {})
    precio = info.get("precio") or p.get("precio_ref") or 0
    return {
        "id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"],
        "nivel": p.get("nivel", "minimo"), "liga": p.get("afiliado") or p.get("url") or "",
        "precio": precio, "rinde": p.get("rinde", 1), "unidad": p.get("unidad", ""),
        "consumo": p.get("consumo", {}), "soloNinos": bool(p.get("solo_con_ninos")),
        "escala": bool(p.get("escala_raciones")), "local": bool(p.get("compra_local")),
        "disponible": info.get("disponible", True), "nota": p.get("nota", ""),
    }


PRODUCTOS = [producto_publico(p) for p in CAT]


def calcular(kit, adultos, ninos):
    """Misma lógica que assets/calculadora.js (mantenerlas iguales)."""
    nivel_max = NIVELES.index(kit)
    raciones = CFG["kits"][kit].get("raciones", 1)
    filas = []
    for p in PRODUCTOS:
        if NIVELES.index(p["nivel"]) > nivel_max:
            continue
        if p["soloNinos"] and ninos == 0:
            continue
        c = p["consumo"]
        u = c.get("fijo", 0) + c.get("por_adulto", 0) * adultos + c.get("por_nino", 0) * ninos
        if p["escala"]:
            u *= raciones
        if u <= 0:
            continue
        paquetes = math.ceil(u / p["rinde"] - 1e-9)
        filas.append({**p, "unidades": u, "paquetes": paquetes,
                      "subtotal": paquetes * p["precio"]})
    total = sum(f["subtotal"] for f in filas if not f["local"])
    return filas, total


# ---------------------------------------------------------------- plantilla
def pagina(titulo, descripcion, cuerpo, camino, jsonld=None, extra_head=""):
    canonica = f"{URL}/{camino}".rstrip("/") + "/" if camino else f"{URL}/"
    ld = ""
    for bloque in (jsonld or []):
        ld += f'<script type="application/ld+json">{json.dumps(bloque, ensure_ascii=False)}</script>\n'
    return f"""<!doctype html>
<html lang="es-MX">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title>
<meta name="description" content="{escape(descripcion)}">
<link rel="canonical" href="{canonica}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(titulo)}">
<meta property="og:description" content="{escape(descripcion)}">
<meta property="og:url" content="{canonica}">
<meta property="og:locale" content="es_MX">
<meta name="theme-color" content="#0f2a3d">
<link rel="icon" href="{ruta('assets/icono.svg')}" type="image/svg+xml">
<link rel="stylesheet" href="{ruta('assets/estilo.css')}">
{ld}{extra_head}</head>
<body>
<header class="barra">
  <a class="marca" href="{ruta()}"><span class="logo">72</span>{escape(CFG['nombre'])}</a>
  <nav>
    <a href="{ruta()}#calculadora">Calculadora</a>
    <a href="{ruta('kits/')}">Kits</a>
    <a href="{ruta('guias/')}">Guías</a>
  </nav>
</header>
<main>
{cuerpo}
</main>
<footer class="pie">
  <p><strong>{escape(CFG['nombre'])}</strong> · {escape(CFG['eslogan'])}</p>
  <p class="aviso">Los botones "Ver en Mercado Libre" son ligas de afiliado: si compras, recibimos una comisión sin costo extra para ti. Los precios se revisan a diario y pueden cambiar; el precio final es el que muestra Mercado Libre. <a href="{ruta('aviso-afiliados/')}">Más información</a> · <a href="{ruta('privacidad/')}">Privacidad</a></p>
</footer>
</body>
</html>
"""


def migas(*pares):
    items = [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{URL}/{c}"}
             for i, (n, c) in enumerate(pares)]
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def tabla_kit(kit, adultos, ninos):
    filas, total = calcular(kit, adultos, ninos)
    html = []
    for cat in ORDEN_CATEGORIAS:
        grupo = [f for f in filas if f["categoria"] == cat]
        if not grupo:
            continue
        html.append(f'<h3 class="cat">{escape(cat)}</h3><ul class="lista">')
        for f in grupo:
            nota = f'<small>{escape(f["nota"])}</small>' if f["nota"] else ""
            if f["local"]:
                accion = '<span class="local">Compra local</span>'
                cant = f'{f["unidades"]:g} {escape(f["unidad"])}'
            else:
                cant = f'{f["paquetes"]} paq. · {dinero(f["subtotal"])}'
                accion = (f'<a class="btn" rel="sponsored nofollow noopener" target="_blank" '
                          f'href="{escape(f["liga"])}">Ver en Mercado Libre</a>')
            html.append(f'<li><div><strong>{escape(f["nombre"])}</strong>{nota}</div>'
                        f'<div class="cant">{cant}</div>{accion}</li>')
        html.append("</ul>")
    return "\n".join(html), total


# ---------------------------------------------------------------- páginas
def escribir(camino, contenido):
    destino = SALIDA / camino / "index.html" if not camino.endswith(".html") else SALIDA / camino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")


def pagina_inicio():
    fam = CFG["familia_default"]
    tarjetas = []
    for k in NIVELES:
        _, total = calcular(k, fam["adultos"], fam["ninos"])
        info = CFG["kits"][k]
        tarjetas.append(f"""<a class="tarjeta" href="{ruta('kits/' + k + '/')}">
  <span class="nivel">{escape(info['nombre'])}</span>
  <span class="precio">desde {dinero(total)}</span>
  <p>{escape(info['descripcion'])}</p></a>""")
    guias = "".join(f'<a class="chip" href="{ruta("guias/" + r + "/")}">{escape(v["titulo"])}</a>'
                    for r, v in RIESGOS.items())
    cuerpo = f"""
<section class="hero">
  <h1>Tu kit de emergencia de 72 horas, calculado para tu familia</h1>
  <p>Dinos cuántos son y te armamos la lista exacta con los productos más baratos de Mercado Libre que llegan rápido. Agua, comida, luz, botiquín y algo para mantener tranquilos a los niños.</p>
  <a class="btn grande" href="#calculadora">Calcular mi kit</a>
</section>

<section id="calculadora" class="calc">
  <h2>Calculadora de kit</h2>
  <div class="controles">
    <label>Adultos <input id="adultos" type="number" min="1" max="12" value="{fam['adultos']}"></label>
    <label>Niños <input id="ninos" type="number" min="0" max="12" value="{fam['ninos']}"></label>
  </div>
  <div class="pestanas" role="tablist">
    {''.join(f'<button role="tab" data-kit="{k}"{" class=activo" if k == "maximo" else ""}>{escape(CFG["kits"][k]["nombre"])}</button>' for k in NIVELES)}
  </div>
  <p id="desc-kit" class="desc"></p>
  <div id="resultado" aria-live="polite"></div>
  <div class="total"><span>Total estimado en Mercado Libre</span><strong id="total">—</strong></div>
  <p class="aviso">Precios revisados automáticamente. El agua marcada como "compra local" no se suma: por su peso conviene comprarla cerca de casa.</p>
</section>

<section class="kits">
  <h2>Tres niveles de preparación</h2>
  <p>Precios para una familia de {fam['adultos']} adultos y {fam['ninos']} niños.</p>
  <div class="rejilla">{''.join(tarjetas)}</div>
</section>

<section class="guias">
  <h2>Guías por tipo de emergencia</h2>
  <div class="chips">{guias}</div>
</section>
<script src="{ruta('assets/catalogo.js')}"></script>
<script src="{ruta('assets/calculadora.js')}"></script>
"""
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": CFG["nombre"],
           "url": f"{URL}/", "inLanguage": "es-MX", "description": CFG["eslogan"]}]
    escribir("", pagina(f"{CFG['nombre']} · Kit de emergencia 72 horas para tu familia",
                        "Calcula y arma tu kit de emergencia de 72 horas para huracán, sismo o inundación con los productos más baratos de Mercado Libre.",
                        cuerpo, "", ld))


def paginas_kits():
    fam = CFG["familia_default"]
    lista = []
    for k in NIVELES:
        info = CFG["kits"][k]
        tabla, total = tabla_kit(k, fam["adultos"], fam["ninos"])
        cuerpo = f"""
<nav class="migas"><a href="{ruta()}">Inicio</a> › <a href="{ruta('kits/')}">Kits</a> › {escape(info['nombre'])}</nav>
<h1>Kit de emergencia {escape(info['nombre'])} para 72 horas</h1>
<p class="lead">{escape(info['descripcion'])}</p>
<p>Lista para una familia de {fam['adultos']} adultos y {fam['ninos']} niños. <a href="{ruta()}#calculadora">Ajústala a tu familia en la calculadora</a>.</p>
{tabla}
<div class="total"><span>Total estimado</span><strong>{dinero(total)}</strong></div>
"""
        ld = [migas(("Inicio", ""), ("Kits", "kits/"), (info["nombre"], f"kits/{k}/"))]
        escribir(f"kits/{k}", pagina(f"Kit de emergencia {info['nombre']} 72 horas · {CFG['nombre']}",
                                     f"Lista completa del kit de emergencia {info['nombre']} para 72 horas con precio total estimado ({dinero(total)} para 4 personas).",
                                     cuerpo, f"kits/{k}/", ld))
        lista.append(f'<li><a href="{ruta("kits/" + k + "/")}">Kit {escape(info["nombre"])}</a> — {escape(info["descripcion"])} Desde {dinero(total)}.</li>')
    cuerpo = f"""<h1>Kits de emergencia de 72 horas</h1><ul class="simple">{''.join(lista)}</ul>"""
    escribir("kits", pagina(f"Kits de emergencia · {CFG['nombre']}",
                            "Compara los kits de emergencia Mínimo, Máximo y Plus para 72 horas.", cuerpo, "kits/"))


def bloque_riesgo(r, lugar=""):
    v = RIESGOS[r]
    consejos = "".join(f"<li>{escape(c)}</li>" for c in v["consejos"])
    faq = "".join(f"<details><summary>{escape(f['p'])}</summary><p>{escape(f['r'])}</p></details>"
                  for f in v["faq"])
    kit = v["kit_sugerido"]
    fam = CFG["familia_default"]
    tabla, total = tabla_kit(kit, fam["adultos"], fam["ninos"])
    html = f"""
<p class="lead">{escape(v['temporada'])}</p>
<h2>Qué hacer para estar listo{escape(lugar)}</h2>
<ul class="simple">{consejos}</ul>
<h2>Kit recomendado: {escape(CFG['kits'][kit]['nombre'])}</h2>
<p>Para {fam['adultos']} adultos y {fam['ninos']} niños, total estimado <strong>{dinero(total)}</strong>. <a href="{ruta()}#calculadora">Calcúlalo para tu familia</a>.</p>
{tabla}
<h2>Preguntas frecuentes</h2>
<div class="faq">{faq}</div>
"""
    ld_faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["p"], "acceptedAnswer": {"@type": "Answer", "text": f["r"]}}
        for f in v["faq"]]}
    return html, ld_faq


def paginas_guias():
    urls = []
    enlaces = []
    for r, v in RIESGOS.items():
        html, ld_faq = bloque_riesgo(r)
        locales = [c for c in CIUDADES if r in c["riesgos"]]
        ligas = "".join(f'<a class="chip" href="{ruta(local_camino(r, c))}">{escape(c["nombre"])}</a>'
                        for c in locales)
        cuerpo = f"""
<nav class="migas"><a href="{ruta()}">Inicio</a> › <a href="{ruta('guias/')}">Guías</a> › {escape(v['titulo'])}</nav>
<h1>{escape(v['titulo'])}: lista completa para 72 horas</h1>
{html}
<h2>Guías por ciudad</h2><div class="chips">{ligas}</div>
"""
        camino = f"guias/{r}/"
        escribir(camino.rstrip("/"), pagina(f"{v['titulo']} · lista y precios | {CFG['nombre']}",
                                            f"{v['titulo']}: qué debe llevar, cuánto cuesta y cómo prepararte con tu familia.",
                                            cuerpo, camino,
                                            [ld_faq, migas(("Inicio", ""), ("Guías", "guias/"), (v["titulo"], camino))]))
        urls.append(camino)
        enlaces.append(f'<li><a href="{ruta(camino)}">{escape(v["titulo"])}</a></li>')
    escribir("guias", pagina(f"Guías de emergencia · {CFG['nombre']}",
                             "Guías para preparar tu kit de emergencia según el riesgo: huracán, sismo e inundación.",
                             f"<h1>Guías de emergencia</h1><ul class='simple'>{''.join(enlaces)}</ul>", "guias/"))
    return urls + ["guias/"]


def local_camino(r, c):
    return f"kit-emergencia-{slug(RIESGOS[r]['nombre'])}-{slug(c['nombre'])}/"


def paginas_locales():
    urls = []
    for c in CIUDADES:
        for r in c["riesgos"]:
            v = RIESGOS[r]
            html, ld_faq = bloque_riesgo(r, f" en {c['nombre']}")
            otras = [x for x in c["riesgos"] if x != r]
            extra = "".join(f'<a class="chip" href="{ruta(local_camino(x, c))}">{escape(RIESGOS[x]["titulo"])} en {escape(c["nombre"])}</a>'
                            for x in otras)
            camino = local_camino(r, c)
            titulo = f"{v['titulo']} en {c['nombre']}, {c['estado']}"
            cuerpo = f"""
<nav class="migas"><a href="{ruta()}">Inicio</a> › <a href="{ruta('guias/' + r + '/')}">{escape(v['titulo'])}</a> › {escape(c['nombre'])}</nav>
<h1>{escape(titulo)}</h1>
<p>Si vives en {escape(c['nombre'])}, el {escape(v['nombre'])} es uno de los riesgos para los que conviene tener un kit listo. Esta es la lista con cantidades y precios para entrega en {escape(c['estado'])}.</p>
{html}
{f'<h2>Otros riesgos en {escape(c["nombre"])}</h2><div class="chips">{extra}</div>' if extra else ''}
"""
            escribir(camino.rstrip("/"), pagina(f"{titulo} | {CFG['nombre']}",
                                                f"Qué debe llevar un {v['titulo'].lower()} en {c['nombre']}: lista, cantidades y precios para tu familia.",
                                                cuerpo, camino,
                                                [ld_faq, migas(("Inicio", ""), (v["titulo"], f"guias/{r}/"), (c["nombre"], camino))]))
            urls.append(camino)
    return urls


def paginas_legales():
    afil = f"""<h1>Aviso sobre ligas de afiliado</h1>
<p>{escape(CFG['nombre'])} participa en el Programa de Afiliados de Mercado Libre. Cuando compras desde un botón "Ver en Mercado Libre" podemos recibir una comisión. El precio que pagas es el mismo.</p>
<p>No vendemos productos directamente. La compra, el pago, el envío, las garantías y las devoluciones se realizan con Mercado Libre y con el vendedor de cada producto, conforme a sus términos.</p>
<p>Los precios mostrados se actualizan automáticamente y son estimados. El precio válido es el que aparece en Mercado Libre al momento de comprar.</p>
<p>La información de este sitio es orientativa y no sustituye las indicaciones de Protección Civil ni de tu médico. Consulta siempre la dosis de cualquier medicamento con un profesional de la salud.</p>"""
    priv = f"""<h1>Aviso de privacidad</h1>
<p>{escape(CFG['nombre'])} no solicita, recaba ni almacena datos personales. La calculadora funciona por completo en tu navegador y no envía la información que capturas.</p>
<p>Al seguir una liga hacia Mercado Libre, ese sitio puede registrar tu visita conforme a su propio aviso de privacidad.</p>
<p>Última actualización: {HOY}.</p>"""
    escribir("aviso-afiliados", pagina(f"Aviso de afiliados · {CFG['nombre']}", "Cómo funcionan las ligas de afiliado de este sitio.", afil, "aviso-afiliados/"))
    escribir("privacidad", pagina(f"Privacidad · {CFG['nombre']}", "Aviso de privacidad.", priv, "privacidad/"))
    escribir("404.html", pagina(f"Página no encontrada · {CFG['nombre']}", "Página no encontrada.",
                                f'<h1>No encontramos esta página</h1><p><a class="btn" href="{ruta()}">Ir a la calculadora</a></p>', ""))


def recursos():
    destino = SALIDA / "assets"
    shutil.copytree(RAIZ / "assets", destino, dirs_exist_ok=True)
    datos = {"kits": CFG["kits"], "niveles": NIVELES, "categorias": ORDEN_CATEGORIAS,
             "simbolo": CFG.get("simbolo", "$"), "productos": PRODUCTOS}
    (destino / "catalogo.js").write_text(
        "window.KIT72=" + json.dumps(datos, ensure_ascii=False) + ";", encoding="utf-8")


def mapa(urls):
    todas = ["", "kits/"] + [f"kits/{k}/" for k in NIVELES] + urls + ["aviso-afiliados/", "privacidad/"]
    filas = "".join(f"<url><loc>{URL}/{u}</loc><lastmod>{HOY}</lastmod></url>" for u in todas)
    (SALIDA / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{filas}</urlset>',
        encoding="utf-8")
    (SALIDA / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}/sitemap.xml\n", encoding="utf-8")
    (SALIDA / ".nojekyll").write_text("", encoding="utf-8")


def main():
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir()
    recursos()
    pagina_inicio()
    paginas_kits()
    urls = paginas_guias() + paginas_locales()
    paginas_legales()
    mapa(urls)
    print(f"Sitio generado en {SALIDA} con {len(urls) + 8} páginas.")


if __name__ == "__main__":
    main()
