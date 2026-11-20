# geoai-felicidad

Demo de **GeoAI** de [Spatialis S.A.S.](https://spatialis.com.co): detección de crecimiento urbano sobre la **Ciudadela La Felicidad** (Fontibón, Bogotá), que pasó de potreros a más de un centenar de edificaciones nuevas en poco más de una década.

En vivo: <https://spatialis-co.github.io/geoai-felicidad/>

## Qué demuestra

Un flujo de GeoAI aplicado a imagen satelital, con dos dispositivos:

1. **Comparación multitemporal** — un *swipe* entre la imagen de **2014** (potreros) y la **actual** (la ciudadela construida). Arrastra el tirador para revelar el cambio.
2. **Detección de cambio** — las edificaciones construidas *después de 2014* aparecen con un revelado animado, clasificadas por tipo (residencial, en construcción, comercial, dotacional, industrial). Clic en cualquiera para ver su huella, pisos, categoría y qué había en ese suelo en 2014.

El panel resume el resultado: **103 edificaciones nuevas desde 2014**, **17 ha** construidas y **10+ años** de cambio.

## Honestidad sobre los datos

Esta es una **demo de producto**, y conviene ser claro sobre de dónde sale cada cosa:

| Elemento | Fuente | Licencia |
|---|---|---|
| Imagen 2014 | Esri World Imagery **Wayback** (release 2014‑02‑20) | Esri |
| Imagen actual | Esri World Imagery | Esri |
| Huellas de edificación | OpenStreetMap | ODbL |

La **detección de cambio sí es real**: cada huella de OpenStreetMap se contrasta, pixel a pixel, contra la imagen satelital de 2014 y se conserva solo si ese suelo estaba **sin construir** (potrero o tierra) en esa fecha. Así, lo que ya existía en 2014 —el C.C. Hayuelos, la zona industrial del sureste— no aparece como crecimiento. El resultado representa el crecimiento del periodo, no un volcado genérico de OSM.

Lo que la demo **no** hace es segmentar las edificaciones directamente del raster: toma las huellas ya vectorizadas de OSM. En un proyecto real, el modelo de Spatialis extrae las huellas de la propia imagen (sin depender de OSM), con control de calidad, y el resultado se integra a la plataforma SIG corporativa del cliente.

`data/edificaciones.geojson` se reconstruye con `tools/detectar_cambios.py` a partir de las huellas de OSM (`tools/osm-buildings-raw.json`) y la imagen Wayback 2014:

```bash
python3 tools/detectar_cambios.py data/edificaciones.geojson
```

El script descarga el mosaico satelital de 2014, clasifica el suelo bajo cada huella (vegetación / tierra / ya construido), marca como nuevas las que estaban sobre suelo libre, calcula su huella (área geodésica sobre la esfera autálica de WGS84) y las ordena por tamaño para que el revelado empiece por las edificaciones grandes. Requiere `Pillow`.

## Cómo está hecho

Página estática. Leaflet se carga desde CDN; la imagen satelital (Esri World Imagery y Wayback) y las teselas son de **acceso anónimo, sin clave de API**. No hay backend.

```bash
python3 -m http.server 8780
```

y abrir <http://localhost:8780>.

Dentro de un `iframe`, la rueda del ratón desplaza la página y solo hace zoom con `Ctrl`. Por debajo de 860 px el panel pasa a hoja inferior y los objetivos táctiles crecen.

## Identidad

Interfaz alineada al sistema oficial de spatialis.com.co: reparto de color 60‑30‑10 (azul corporativo, acento esmeralda `#34D399`), tipografías Nunito y JetBrains Mono, e isotipo oficial. `assets/spatialis-ui.css` es la misma hoja que usan los demás demos de Spatialis.

## Licencia

Código de demostración, todos los derechos reservados (archivo `LICENSE`). Imagen © Esri y proveedores; edificaciones © colaboradores de OpenStreetMap (ODbL). Las librerías de terceros conservan sus licencias.

## Contacto

Spatialis S.A.S. · <https://spatialis.com.co> · desarrollo@spatialis.com.co
