#!/usr/bin/env python3
"""Actualiza precios y disponibilidad desde la API de Mercado Libre.

Escribe datos/precios.json y datos/reporte.md (lo que el robot te avisa en GitHub).
Nunca rompe la publicación: si la API falla, se conservan los últimos precios conocidos.

Credenciales (opcionales, como Secrets del repo):
  ML_CLIENT_ID, ML_CLIENT_SECRET   -> app registrada en developers.mercadolibre.com.mx
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
API = "https://api.mercadolibre.com"
PRECIOS = RAIZ / "datos" / "precios.json"
REPORTE = RAIZ / "datos" / "reporte.md"


def http_json(url, token=None, data=None):
    headers = {"Accept": "application/json", "User-Agent": "kit72-bot"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


REDIRECT_URI = "https://jorch01.github.io/kit72/"
AVISOS_TOKEN = []


def ocultar(valor):
    """Evita que GitHub muestre el valor en los registros."""
    if valor and os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{valor}")


def guardar_refresh(nuevo):
    """Deja el nuevo refresh token en un archivo temporal (fuera del repo) para
    que el workflow lo guarde como Secret. Mercado Libre lo cambia en cada uso."""
    destino = os.environ.get("RUNNER_TEMP")
    if not destino or not nuevo:
        return
    Path(destino, "ml_refresh_token").write_text(nuevo, encoding="utf-8")


def pedir_token(datos):
    try:
        r = http_json(f"{API}/oauth/token", data=datos)
    except urllib.error.HTTPError as e:
        cuerpo = ""
        try:
            cuerpo = e.read().decode()[:200]
        except Exception:  # noqa: BLE001
            pass
        AVISOS_TOKEN.append(f"Mercado Libre rechazó la autorización ({datos['grant_type']}): HTTP {e.code} {cuerpo}")
        return None
    except Exception as e:  # noqa: BLE001
        AVISOS_TOKEN.append(f"No se pudo pedir el token ({datos['grant_type']}): {e}")
        return None
    ocultar(r.get("access_token"))
    ocultar(r.get("refresh_token"))
    guardar_refresh(r.get("refresh_token"))
    return r.get("access_token")


def obtener_token():
    """Prioridad: código de autorización recién dado > refresh token guardado > token de la app."""
    cid, secret = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not (cid and secret):
        return None
    base = {"client_id": cid, "client_secret": secret}
    codigo = (os.environ.get("ML_AUTH_CODE") or "").strip()
    if codigo:
        ocultar(codigo)
        token = pedir_token({**base, "grant_type": "authorization_code", "code": codigo,
                             "redirect_uri": REDIRECT_URI})
        if token:
            print("Autorización de la cuenta registrada correctamente.")
            return token
    refresh = (os.environ.get("ML_REFRESH_TOKEN") or "").strip()
    if refresh:
        ocultar(refresh)
        token = pedir_token({**base, "grant_type": "refresh_token", "refresh_token": refresh})
        if token:
            return token
        AVISOS_TOKEN.append("La autorización de tu cuenta caducó o no se guardó: vuelve a autorizar la app (ver README).")
    return pedir_token({**base, "grant_type": "client_credentials"})


def consultar(prod, token):
    """Devuelve (precio, disponible, titulo) o lanza excepción."""
    pid = prod["ml_id"]
    if prod.get("ml_tipo") == "producto":
        try:
            d = http_json(f"{API}/products/{pid}", token)
            bbw = d.get("buy_box_winner") or {}
            if bbw.get("price"):
                return bbw.get("price"), d.get("status", "active") == "active", d.get("name")
        except urllib.error.HTTPError:
            pass
        # Alternativa: publicaciones activas de ese producto de catálogo
        d = http_json(f"{API}/products/{pid}/items", token)
        res = d.get("results") or []
        precios = [r.get("price") for r in res if r.get("price")]
        return (min(precios) if precios else None), bool(precios), None
    # Publicación normal: primero multiget; si Mercado Libre lo bloquea, el recurso de precios
    try:
        d = http_json(f"{API}/items?ids={pid}&attributes=id,price,status,available_quantity,title", token)
        item = (d[0] if isinstance(d, list) and d else {})
        if item.get("code") == 200:
            b = item["body"]
            disponible = b.get("status") == "active" and (b.get("available_quantity") or 0) > 0
            return b.get("price"), disponible, b.get("title")
    except urllib.error.HTTPError:
        pass
    try:
        d = http_json(f"{API}/items/{pid}/sale_price?context=channel_marketplace", token)
        if d.get("amount"):
            return d["amount"], True, None
    except urllib.error.HTTPError:
        pass
    d = http_json(f"{API}/items/{pid}/prices", token)
    precios = [x.get("amount") for x in (d.get("prices") or []) if x.get("amount")]
    if not precios:
        raise urllib.error.HTTPError(f"{API}/items/{pid}/prices", 404, "sin precio", None, None)
    return min(precios), True, None


def main():
    cfg = yaml.safe_load((RAIZ / "config" / "sitio.yaml").read_text(encoding="utf-8"))
    cat = yaml.safe_load((RAIZ / "catalogo" / "productos.yaml").read_text(encoding="utf-8"))
    previos = json.loads(PRECIOS.read_text(encoding="utf-8")) if PRECIOS.exists() else {}
    token = obtener_token()
    print("Token de Mercado Libre:", "obtenido" if token else "NO obtenido (se consulta sin token)")
    umbral = float(cfg.get("alerta_alza_pct", 25))
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    nuevos, agotados, alzas, errores, sin_liga = dict(previos), [], [], [], []
    manuales = []
    consultados = 0
    for p in cat["productos"]:
        if p.get("compra_local"):
            continue
        if not p.get("afiliado") and not p.get("sin_comision"):
            sin_liga.append(p)
        if not p.get("ml_id"):
            continue
        if p.get("ml_tipo") != "producto":
            # Mercado Libre no permite consultar publicaciones sueltas de otros vendedores;
            # solo los productos de catálogo (/p/MLM...). Estas quedan con precio de referencia.
            manuales.append(p)
            continue
        try:
            precio, disponible, titulo = consultar(p, token)
            consultados += 1
        except urllib.error.HTTPError as e:
            detalle = ""
            try:
                detalle = (e.read() or b"").decode()[:150] if e.fp else str(e.msg)[:150]
            except Exception:  # noqa: BLE001
                detalle = str(e.msg)[:150]
            errores.append(f"{p['id']}: HTTP {e.code} {detalle}")
            continue
        except Exception as e:  # noqa: BLE001
            errores.append(f"{p['id']}: {e}")
            continue
        anterior = (previos.get(p["id"]) or {}).get("precio") or p.get("precio_ref")
        nuevos[p["id"]] = {"precio": precio, "disponible": disponible,
                           "titulo_ml": titulo, "actualizado": ahora}
        if not disponible:
            agotados.append(p)
        elif precio and anterior and precio > anterior * (1 + umbral / 100):
            alzas.append((p, anterior, precio))

    PRECIOS.parent.mkdir(exist_ok=True)
    PRECIOS.write_text(json.dumps(nuevos, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- Reporte para el aviso de GitHub ----------
    lineas = [f"Revisión automática del {ahora}. Productos consultados: {consultados}. Token: {'sí' if token else 'no'}.", ""]
    accion = False
    if agotados:
        accion = True
        lineas.append("## Agotados o pausados (cámbialos en catalogo/productos.yaml)")
        for p in agotados:
            q = urllib.parse.quote(p["nombre"])
            lineas.append(f"- **{p['nombre']}** (`{p['id']}`) — "
                          f"[buscar reemplazo con envío Full](https://listado.mercadolibre.com.mx/{q}_Envio_Full_OrderId_PRICE_NoIndex_True)")
        lineas.append("")
    if alzas:
        accion = True
        lineas.append(f"## Subieron más de {umbral:.0f}%")
        for p, a, n in alzas:
            lineas.append(f"- **{p['nombre']}**: ${a:,.0f} → ${n:,.0f}")
        lineas.append("")
    if sin_liga:
        accion = True
        lineas.append("## Sin liga de afiliado (no estás cobrando comisión)")
        lineas.append("Copia estas URLs, pégalas juntas en el Generador de links y pon cada liga en el campo `afiliado`:")
        lineas.append("```")
        lineas += [p["url"] for p in sin_liga if p.get("url")]
        lineas.append("```")
        lineas.append("")
    if manuales:
        lineas.append("## Con precio de referencia (sin revisión automática)")
        lineas.append("Mercado Libre solo deja revisar productos de catálogo (ligas /p/MLM...). "
                      "Si encuentras la versión de catálogo de alguno, cámbialo y quedará automático:")
        lineas += [f"- {p['nombre']}" for p in manuales]
        lineas.append("")
    if AVISOS_TOKEN and not consultados:
        accion = True
        lineas.append("## Problema con la autorización de Mercado Libre")
        lineas += [f"- {a}" for a in AVISOS_TOKEN]
        lineas.append("")
    if errores:
        lineas.append("## No se pudieron consultar")
        lineas.append("Si son todos, revisa la autorización de la app (sección «Precios automáticos» del README).")
        lineas += [f"- {e}" for e in errores]
        lineas.append("")
    if not accion and not errores:
        lineas.append("Todo en orden: no hay nada que hacer.")
    REPORTE.write_text("\n".join(lineas), encoding="utf-8")

    # Señal para el workflow: abrir aviso solo si hay algo que hacer
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a", encoding="utf-8") as f:
            f.write(f"requiere_accion={'true' if accion else 'false'}\n")
    print("\n".join(lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
