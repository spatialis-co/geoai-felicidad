# geoai-felicidad

Demo de **GeoAI** de [Spatialis S.A.S.](https://spatialis.co): detección de crecimiento urbano sobre la **Ciudadela La Felicidad** (Fontibón, Bogotá), que pasó de potreros a más de 200 edificaciones en poco más de una década.

En vivo: <https://spatialis-co.github.io/geoai-felicidad/>

## Qué demuestra

Un flujo de GeoAI aplicado a imagen satelital, con dos dispositivos:

1. **Comparación multitemporal** — un *swipe* entre la imagen de **2014** (potreros) y la **actual** (la ciudadela construida). Arrastra el tirador para revelar el cambio.
2. **Extracción de edificaciones** — las construcciones aparecen con un revelado animado, clasificadas por tipo (residencial, en construcción, comercial, dotacional, industrial), como la salida de un modelo de detección sobre la imagen. Clic en cualquiera para ver su huella, pisos y categoría.

El panel resume el resultado: **230 edificaciones**, **46 ha** de huella construida y **10+ años** de cambio.

## Honestidad sobre los datos

Esta es una **demo de producto**, y conviene ser claro sobre de dónde sale cada cosa:

| Elemento | Fuente | Licencia |
|---|---|---|
| Imagen 2014 | Esri World Imagery **Wayback** (release 2014‑02‑20) | Esri |
| Imagen actual | Esri World Imagery | Esri |
| Huellas de edificación | OpenStreetMap | ODbL |

Las huellas provienen de OpenStreetMap y en la demo **representan** la salida de un modelo de extracción de edificaciones. En un proyecto real, el modelo de Spatialis las extrae directamente de la imagen satelital, con control de calidad, y el resultado se integra a la plataforma SIG corporativa del cliente. La demo no ejecuta un modelo en el navegador: muestra, con datos reales y verificables, cómo se ve y se usa ese resultado.

`data/edificaciones.geojson` (79 KB) se reconstruye con `tools/build_edificaciones.py` a partir de la respuesta de OpenStreetMap incluida en `tools/osm-buildings-raw.json`:

```bash
python3 tools/build_edificaciones.py data/edificaciones.geojson
```

El script clasifica cada edificación, calcula su huella (área geodésica sobre la esfera autálica de WGS84) y las ordena por tamaño para que el revelado empiece por las torres grandes.

## Cómo está hecho

Página estática. Leaflet se carga desde CDN; la imagen satelital (Esri World Imagery y Wayback) y las teselas son de **acceso anónimo, sin clave de API**. No hay backend.

```bash
python3 -m http.server 8780
```

y abrir <http://localhost:8780>.

Dentro de un `iframe`, la rueda del ratón desplaza la página y solo hace zoom con `Ctrl`. Por debajo de 860 px el panel pasa a hoja inferior y los objetivos táctiles crecen.

## Identidad

Interfaz alineada al sistema oficial de spatialis.co: reparto de color 60‑30‑10 (azul corporativo, acento esmeralda `#34D399`), tipografías Nunito y JetBrains Mono, e isotipo oficial. `assets/spatialis-ui.css` es la misma hoja que usan los demás demos de Spatialis.

## Licencia

Código de demostración, todos los derechos reservados (archivo `LICENSE`). Imagen © Esri y proveedores; edificaciones © colaboradores de OpenStreetMap (ODbL). Las librerías de terceros conservan sus licencias.

## Contacto

Spatialis S.A.S. · <https://spatialis.co> · desarrollo@spatialis.com.co
