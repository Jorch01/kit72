# Kit72

Sitio de kits de emergencia de 72 horas con ligas de afiliado de Mercado Libre.
Se publica gratis en GitHub Pages: **https://jorch01.github.io/kit72/**

## Cómo funciona

- `catalogo/productos.yaml` es lo único que editas: qué productos van en cada kit, su liga de afiliado y cuánto se necesita por persona.
- Todos los días, GitHub Actions revisa precios y existencias en Mercado Libre, recalcula los kits y vuelve a publicar el sitio.
- Si un producto se agota, sube de precio o le falta la liga de afiliado, el robot abre un aviso (Issue) titulado **"Kit72: productos por revisar"** con lo que hay que hacer.
- El sitio genera solo las páginas de SEO: una por kit, por tipo de riesgo y por ciudad (`config/ciudades.yaml`), más `sitemap.xml`.

## Puesta en marcha (una sola vez)

1. **Crear el repo** `kit72` en tu cuenta Jorch01 (público, sin README) y subir estos archivos.
2. **Activar Pages:** Settings → Pages → Source: **GitHub Actions**.
3. **Permisos del robot:** Settings → Actions → General → Workflow permissions → **Read and write permissions**.
4. **Primera publicación:** pestaña Actions → "Actualizar precios y publicar" → **Run workflow**. En unos 2 minutos el sitio queda en https://jorch01.github.io/kit72/
5. **Ligas de afiliado:** abre el aviso que crea el robot, copia la lista de URLs, pégala completa en el [Generador de links](https://www.mercadolibre.com.mx/afiliados/linkbuilder) y pon cada liga en el campo `afiliado` del producto.
6. **Precios en automático (recomendado):** registra una app gratuita en https://developers.mercadolibre.com.mx y guarda `ML_CLIENT_ID` y `ML_CLIENT_SECRET` en Settings → Secrets and variables → Actions. Sin esto el sitio funciona con los precios de referencia del catálogo.
7. **Google:** da de alta el sitio en Google Search Console y envía `https://jorch01.github.io/kit72/sitemap.xml`.

## Tu rutina

Cuando llegue un aviso del robot:

- **Producto agotado:** usa la liga "buscar reemplazo" del aviso, elige uno con envío Full, cambia `url`, `ml_id`, `ml_tipo`, `precio_ref` y `afiliado` en el catálogo.
- **Producto nuevo:** copia un bloque existente en `productos.yaml` y ajústalo. Puedes editar directo en github.com (ícono del lápiz) y guardar con "Commit changes"; el sitio se republica solo.

## Reglas del catálogo

- `ml_tipo: producto` si la URL es `mercadolibre.com.mx/p/MLM…`; `ml_tipo: item` si es `articulo.mercadolibre.com.mx/MLM-123…` (en `ml_id` va sin guion: `MLM123…`).
- Usa productos con envío Full y vendedores nacionales: los internacionales no pagan comisión.
- `consumo` es la cantidad total para 72 horas; `rinde` es cuántas unidades trae el paquete. El sitio redondea hacia arriba.

## Probar en tu computadora (opcional)

```
pip install pyyaml
python scripts/generar_sitio.py
python -m http.server -d _site 8000
```
Ojo: en local las rutas usan `/kit72/`, así que abre `http://localhost:8000/` solo para revisar el HTML generado.

## Estructura

```
catalogo/productos.yaml   productos y cantidades (lo que editas)
config/sitio.yaml         nombre, URL, kits y umbral de alertas
config/ciudades.yaml      ciudades para páginas locales
config/riesgos.yaml       textos por huracán, sismo e inundación
scripts/                  robot de precios y generador del sitio
assets/                   estilos y calculadora
datos/                    precios y reporte que escribe el robot
```
