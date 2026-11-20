#!/usr/bin/env python3
"""Detección de cambios 2014 -> hoy sobre la Ciudadela La Felicidad.

Insumos:
  - tools/osm-buildings-raw.json : huellas de edificación actuales (OSM, ODbL).
  - Imagen satelital Esri World Imagery Wayback (release 10, 2014-02-20) y actual.

Qué hace, de verdad:
  Para cada huella de edificación de hoy, muestrea la imagen satelital de 2014
  justo debajo de ese polígono y clasifica qué había entonces (vegetación /
  suelo descubierto / ya construido). Si en 2014 ese suelo estaba sin construir,
  la edificación se marca como NUEVA desde 2014 -> es un cambio detectado.

  Así el GeoJSON de salida representa el crecimiento real del periodo, no un
  volcado genérico de OSM: las bodegas e hitos que ya existían en 2014
  (Hayuelos, Jumbo, Easy, la zona industrial) quedan como 'existente'.

Salida: data/edificaciones.geojson (solo los cambios, nuevo=True), con el área
geodésica, la categoría, los niveles y qué había en el suelo en 2014.
"""
import io
import json
import math
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PREC = 6
RADIO = 6371007.2  # esfera autalica WGS84
Z = 17             # zoom de muestreo

TESELA_2014 = ("https://wayback.maptiles.arcgis.com/arcgis/rest/services/"
               "World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/10/{z}/{y}/{x}")
TESELA_HOY = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
              "World_Imagery/MapServer/tile/{z}/{y}/{x}")

CATEGORIA = {
    "apartments": "residencial", "residential": "residencial", "house": "residencial",
    "detached": "residencial", "construction": "construccion", "commercial": "comercial",
    "retail": "comercial", "office": "comercial", "warehouse": "industrial",
    "industrial": "industrial", "school": "dotacional", "college": "dotacional",
    "university": "dotacional", "hospital": "dotacional", "civic": "dotacional",
    "roof": "otro", "yes": "otro",
}

UA = {"User-Agent": "Mozilla/5.0 (Spatialis GeoAI demo)"}


# --------------------------------------------------------------- teselas / mosaico

def num_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def bajar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read()


class Mosaico:
    """Mosaico de teselas con georreferencia pixel <-> lon/lat (Web Mercator)."""

    def __init__(self, plantilla, z, x0, x1, y0, y1):
        self.z, self.x0, self.y0 = z, x0, y0
        ancho, alto = (x1 - x0 + 1), (y1 - y0 + 1)
        self.img = Image.new("RGB", (ancho * 256, alto * 256), (30, 30, 30))
        tareas = [(tx, ty) for ty in range(y0, y1 + 1) for tx in range(x0, x1 + 1)]

        def una(t):
            tx, ty = t
            try:
                data = bajar(plantilla.format(z=z, x=tx, y=ty))
                return t, Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                return t, None

        with ThreadPoolExecutor(max_workers=8) as ex:
            for (tx, ty), im in ex.map(una, tareas):
                if im is not None:
                    self.img.paste(im, ((tx - x0) * 256, (ty - y0) * 256))
        self.px = self.img.load()
        self.w, self.h = self.img.size

    def pixel(self, lon, lat):
        fx, fy = num_tile(lon, lat, self.z)
        x = int(round((fx - self.x0) * 256))
        y = int(round((fy - self.y0) * 256))
        return x, y

    def muestra(self, lon, lat):
        x, y = self.pixel(lon, lat)
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[x, y]
        return None


# --------------------------------------------------------------- geometría

def area_anillo(anillo):
    n = len(anillo) - 1
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = anillo[i]
        x2, y2 = anillo[(i + 1) % n]
        total += math.radians(x2 - x1) * (
            2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(total * RADIO * RADIO / 2.0)


def centroide(anillo):
    cx = cy = f = 0.0
    for i in range(len(anillo) - 1):
        x1, y1 = anillo[i]
        x2, y2 = anillo[i + 1]
        cr = x1 * y2 - x2 * y1
        f += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    if f == 0:
        return [round(anillo[0][0], PREC), round(anillo[0][1], PREC)]
    return [round(cx / (3 * f), PREC), round(cy / (3 * f), PREC)]


def en_poligono(x, y, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i]
        xj, yj = anillo[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            dentro = not dentro
        j = i
    return dentro


def puntos_interiores(anillo, k=5):
    """Rejilla de puntos lon/lat dentro del polígono para muestrear la imagen."""
    xs = [p[0] for p in anillo]
    ys = [p[1] for p in anillo]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pts = []
    for i in range(1, k + 1):
        for j in range(1, k + 1):
            x = x0 + (x1 - x0) * i / (k + 1)
            y = y0 + (y1 - y0) * j / (k + 1)
            if en_poligono(x, y, anillo):
                pts.append((x, y))
    if not pts:  # polígono muy fino: usa el centroide
        pts = [centroide(anillo)]
    return pts


# --------------------------------------------------------------- clasificación 2014

def clase_suelo(rgb):
    """Qué es un pixel de imagen satelital: vegetacion / suelo / construido."""
    r, g, b = rgb
    brillo = (r + g + b) / 3.0
    verde = g - max(r, b)
    calido = r - b                   # positivo => marrón/tierra; ~0 => gris
    if verde > 6:
        return "vegetacion"
    if r - g > 42 and r > 105:
        return "construido"          # techo rojo saturado (teja)
    # gris neutro (techo metálico, concreto, pavimento): poca diferencia R-B
    if calido <= 10 and abs(r - g) <= 12:
        return "construido"
    # marrón cálido y no muy claro => tierra/potrero seco
    if r >= g >= b and calido >= 12 and brillo <= 155:
        return "suelo"
    if brillo > 150:
        return "construido"          # superficie clara (cubierta/pavimento)
    return "construido"


def clasificar(mosaico, anillo):
    pts = puntos_interiores(anillo, 5)
    conteo = {"vegetacion": 0, "suelo": 0, "construido": 0}
    for lon, lat in pts:
        px = mosaico.muestra(lon, lat)
        if px is None:
            continue
        conteo[clase_suelo(px)] += 1
    total = sum(conteo.values()) or 1
    natural = conteo["vegetacion"] + conteo["suelo"]
    dominante = max(conteo, key=conteo.get)
    return natural / total, conteo["construido"] / total, dominante


def main(destino):
    crudo = json.load(open(os.path.join(AQUI, "osm-buildings-raw.json"), encoding="utf-8"))
    ways = [e for e in crudo.get("elements", []) if e.get("type") == "way" and e.get("geometry")]

    lons = [p["lon"] for e in ways for p in e["geometry"]]
    lats = [p["lat"] for e in ways for p in e["geometry"]]
    x0, _ = num_tile(min(lons), max(lats), Z)
    x1, _ = num_tile(max(lons), min(lats), Z)
    _, y0 = num_tile(min(lons), max(lats), Z)
    _, y1 = num_tile(max(lons), min(lats), Z)
    x0, x1 = int(x0) - 1, int(x1) + 1
    y0, y1 = int(y0) - 1, int(y1) + 1
    print("mosaico z%d  x[%d..%d] y[%d..%d]  (%d teselas)" %
          (Z, x0, x1, y0, y1, (x1 - x0 + 1) * (y1 - y0 + 1)))

    print("descargando imagen 2014 (Wayback 2014-02-20)...")
    m2014 = Mosaico(TESELA_2014, Z, x0, x1, y0, y1)
    print("descargando imagen actual...")
    mhoy = Mosaico(TESELA_HOY, Z, x0, x1, y0, y1)

    feats = []
    nuevos = 0
    area_nueva = 0.0
    por_cat = {}
    por_suelo = {"vegetacion": 0, "suelo": 0, "construido": 0}

    for e in ways:
        anillo = [[round(p["lon"], PREC), round(p["lat"], PREC)] for p in e["geometry"]]
        if len(anillo) < 4:
            continue
        if anillo[0] != anillo[-1]:
            anillo.append(anillo[0])

        t = e.get("tags", {})
        b = t.get("building", "yes")
        cat = CATEGORIA.get(b, "otro")
        niveles = int(t["building:levels"]) if str(t.get("building:levels", "")).isdigit() else None
        area = area_anillo(anillo)

        frac_natural, _, dominante = clasificar(m2014, anillo)
        _, frac_build_hoy, _ = clasificar(mhoy, anillo)
        # cambio real: el suelo bajo la huella estaba libre (vegetación/tierra)
        # en 2014. Un leve respaldo con la imagen de hoy descarta polígonos que
        # hoy no muestran nada edificado (p. ej. una cancha mal etiquetada).
        nuevo = frac_natural >= 0.5 and frac_build_hoy >= 0.2
        por_suelo[dominante] = por_suelo.get(dominante, 0) + 1

        feats.append({
            "type": "Feature",
            "id": e["id"],
            "properties": {
                "cat": cat,
                "tipo": b,
                "niveles": niveles,
                "nombre": t.get("name") or "",
                "area_m2": round(area),
                "nuevo": nuevo,
                "suelo_2014": dominante,     # qué había en 2014 bajo la huella
                "centro": centroide(anillo),
            },
            "geometry": {"type": "Polygon", "coordinates": [anillo]},
        })
        if nuevo:
            nuevos += 1
            area_nueva += area
            por_cat[cat] = por_cat.get(cat, 0) + 1

    # solo los cambios: edificaciones construidas sobre suelo libre de 2014
    cambios = [f for f in feats if f["properties"]["nuevo"]]
    cambios.sort(key=lambda f: -f["properties"]["area_m2"])

    fc = {
        "type": "FeatureCollection",
        "name": "la_felicidad_cambios_2014_hoy",
        "attribution": "Huellas OpenStreetMap (ODbL); cambio detectado vs. Esri World Imagery Wayback 2014-02-20. Spatialis S.A.S.",
        "periodo": {"desde": "2014-02-20", "hasta": "hoy"},
        "features": cambios,
    }
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))

    print("edificaciones OSM totales: %d" % len(feats))
    print("NUEVAS desde 2014 (cambios): %d" % nuevos)
    print("  por categoria: %s" % por_cat)
    print("  suelo 2014 (todas): %s" % por_suelo)
    print("area construida nueva: %.1f ha" % (area_nueva / 10000))
    print("%.0f KB -> %s" % (os.path.getsize(destino) / 1024, destino))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "data", "edificaciones.geojson"))
