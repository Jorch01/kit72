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


def obtener_token():
    cid, secret = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not (cid and secret):
        return None
    try:
        r = http_json(f"{API}/oauth/token", data={
            "grant_type": "client_credentials", "client_id": cid, "client_secret": secret})
        return r.get("access_token")
    except Exception as e:  # noqa: BLE001
        print(f"[aviso] No se obtuvo token de ML: {e}")
        return None


def consultar(prod, token):
    """Devuelve (precio, disponible, titulo) o lanza excepción."""
    pid = prod["ml_id"]
    if prod.get("ml_tipo") == "producto":
        d = http_json(f"{API}/products/{pid}", token)
        bbw = d.get("buy_box_winner") or {}
        precio = bbw.get("price")
        disponible = bool(bbw) and d.get("status", "active") == "active"
        return precio, disponible, d.get("name")
    d = http_json(f"{API}/items/{pid}", token)
    disponible = d.get("status") == "active" and (d.get("available_quantity") or 0) > 0
    return d.get("price"), disponible, d.get("title")


def main():
    cfg = yaml.safe_load((RAIZ / "config" / "sitio.yaml").read_text(encoding="utf-8"))
    cat = yaml.safe_load((RAIZ / "catalogo" / "productos.yaml").read_text(encoding="utf-8"))
    previos = json.loads(PRECIOS.read_text(encoding="utf-8")) if PRECIOS.exists() else {}
    token = obtener_token()
    umbral = float(cfg.get("alerta_alza_pct", 25))
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    nuevos, agotados, alzas, errores, sin_liga = dict(previos), [], [], [], []
    consultados = 0
    for p in cat["productos"]:
        if p.get("compra_local"):
            continue
        if not p.get("afiliado") and not p.get("sin_comision"):
            sin_liga.append(p)
        if not p.get("ml_id"):
            continue
        try:
            precio, disponible, titulo = consultar(p, token)
            consultados += 1
        except urllib.error.HTTPError as e:
            errores.append(f"{p['id']}: HTTP {e.code}")
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
    lineas = [f"Revisión automática del {ahora}. Productos consultados: {consultados}.", ""]
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
    if errores:
        lineas.append("## No se pudieron consultar")
        lineas.append("Si son todos, revisa los Secrets ML_CLIENT_ID y ML_CLIENT_SECRET.")
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
