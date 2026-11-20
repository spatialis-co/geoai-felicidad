#!/usr/bin/env python3
"""Convierte las edificaciones OSM de la Ciudadela La Felicidad a GeoJSON.

Entrada: respuesta cruda de Overpass (out geom) en osm-buildings-raw.json.
Salida: un GeoJSON ligero con una categoría, los niveles y el área de cada
edificación, listo para servir estático.

Las huellas provienen de OpenStreetMap (ODbL). En la demo representan la salida
de un modelo de extracción de edificaciones sobre imagen satelital; se anota
así con honestidad en el visor y el README.
"""
import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PREC = 6
RADIO = 6371007.2  # esfera autalica WGS84

# building=* -> categoria del visor
CATEGORIA = {
    "apartments": "residencial",
    "residential": "residencial",
    "house": "residencial",
    "detached": "residencial",
    "construction": "construccion",
    "commercial": "comercial",
    "retail": "comercial",
    "office": "comercial",
    "warehouse": "industrial",
    "industrial": "industrial",
    "school": "dotacional",
    "college": "dotacional",
    "university": "dotacional",
    "hospital": "dotacional",
    "civic": "dotacional",
    "roof": "otro",
    "yes": "otro",
}


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


def main(destino):
    crudo = json.load(open(os.path.join(AQUI, "osm-buildings-raw.json"), encoding="utf-8"))
    feats = []
    area_total = 0.0
    por_cat = {}

    for e in crudo.get("elements", []):
        if e.get("type") != "way" or not e.get("geometry"):
            continue
        anillo = [[round(p["lon"], PREC), round(p["lat"], PREC)] for p in e["geometry"]]
        if len(anillo) < 4:
            continue
        if anillo[0] != anillo[-1]:
            anillo.append(anillo[0])

        t = e.get("tags", {})
        b = t.get("building", "yes")
        cat = CATEGORIA.get(b, "otro")
        niveles = None
        if str(t.get("building:levels", "")).isdigit():
            niveles = int(t["building:levels"])

        area = area_anillo(anillo)
        area_total += area
        por_cat[cat] = por_cat.get(cat, 0) + 1

        feats.append({
            "type": "Feature",
            "id": e["id"],
            "properties": {
                "cat": cat,
                "tipo": b,
                "niveles": niveles,
                "nombre": t.get("name") or "",
                "area_m2": round(area),
                "centro": centroide(anillo),
            },
            "geometry": {"type": "Polygon", "coordinates": [anillo]},
        })

    # las de mayor área primero: el "escaneo" revela antes las torres grandes
    feats.sort(key=lambda f: -f["properties"]["area_m2"])

    fc = {
        "type": "FeatureCollection",
        "name": "la_felicidad_edificaciones",
        "attribution": "OpenStreetMap (ODbL) - preparado por Spatialis S.A.S.",
        "features": feats,
    }
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))

    print("edificaciones: %d" % len(feats))
    print("por categoria: %s" % por_cat)
    print("area construida (huella): %.1f ha" % (area_total / 10000))
    print("%.0f KB -> %s" % (os.path.getsize(destino) / 1024, destino))


if __name__ == "__main__":
    main(sys.argv[1])
