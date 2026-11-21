/* ==========================================================================
   GeoAI · Detección de crecimiento urbano — Ciudadela La Felicidad (Bogotá)
   Spatialis S.A.S.

   Dos dispositivos narrativos sobre la misma zona:
     1) swipe de imagen satelital 2014 ↔ hoy (de lotes a ciudadela),
     2) revelado animado de las edificaciones "detectadas" sobre la imagen.

   Las huellas provienen de OpenStreetMap (ODbL) y aquí representan la salida
   de un modelo de extracción de edificaciones; así se declara en el visor.
   ========================================================================== */

(function () {
  "use strict";

  var CENTRO = [4.6555, -74.127];
  var DATOS = "data/edificaciones.geojson";

  /* Imagen satelital, ambas de Esri y sin clave:
     - 2014 desde el servicio Wayband (release 10, 2014-02-20),
     - actual desde World Imagery. */
  var TESELAS_2014 =
    "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/10/{z}/{y}/{x}";
  var TESELAS_HOY =
    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

  var CLASES = {
    residencial: { color: "#00c7fd", etiqueta: "Residencial (torres)" },
    construccion: { color: "#fbbf24", etiqueta: "En construcción" },
    comercial: { color: "#0071c5", etiqueta: "Comercial / oficinas" },
    dotacional: { color: "#34d399", etiqueta: "Dotacional" },
    industrial: { color: "#94a3b8", etiqueta: "Industrial / bodega" },
    otro: { color: "#cbd5e1", etiqueta: "Otras" },
  };

  /* qué había bajo la huella en la imagen de 2014 */
  var SUELO_2014 = {
    vegetacion: "Lote / vegetación",
    suelo: "Suelo descubierto",
    construido: "Ya edificado",
  };

  var map, capaHuellas, handleX = 0.5, datos = null;
  var paneDespues, divHandle;

  /* ----------------------------------------------------------- contadores */

  function animarContador(el, fin, dur, suf) {
    var t0 = performance.now();
    (function paso(t) {
      var k = Math.min(1, (t - t0) / dur);
      var val = Math.round(fin * (1 - Math.pow(1 - k, 3)));
      el.textContent = val.toLocaleString("es-CO") + (suf || "");
      if (k < 1) requestAnimationFrame(paso);
    })(t0);
  }

  function lanzarContadores() {
    document.querySelectorAll("[data-contador]").forEach(function (el) {
      animarContador(el, parseInt(el.dataset.fin, 10), 1400, el.dataset.suf || "");
    });
  }

  /* -------------------------------------------------------------- swipe */

  function colocarSwipe(fraccion) {
    handleX = Math.max(0.05, Math.min(0.95, fraccion));
    var size = map.getSize();
    var px = Math.round(size.x * handleX);
    /* La capa "hoy" se recorta para verse solo a la DERECHA del tirador.
       Se usa la propiedad `clip` (no `clip-path`) y en coordenadas de capa:
       los paneles de Leaflet no tienen tamaño propio —los tiles se desbordan—
       y viven dentro del map-pane trasladado, así que clip-path sobre ellos no
       recorta de forma fiable. Es la técnica del plugin oficial side-by-side. */
    var nw = map.containerPointToLayerPoint([0, 0]);
    var se = map.containerPointToLayerPoint([size.x, size.y]);
    var corte = map.containerPointToLayerPoint([px, 0]).x;
    paneDespues.style.clip = "rect(" + [nw.y, se.x, se.y, corte].join("px,") + "px)";
    divHandle.style.left = px + "px";
    var antes = document.querySelector(".epoca--antes");
    var hoy = document.querySelector(".epoca--hoy");
    if (antes) antes.style.opacity = handleX > 0.16 ? "1" : "0";
    if (hoy) hoy.style.opacity = handleX < 0.84 ? "1" : "0";
  }

  function crearHandle() {
    divHandle = L.DomUtil.create("div", "swipe-handle", map.getContainer());
    divHandle.innerHTML = '<span class="swipe-handle__linea"></span>' +
      '<span class="swipe-handle__grip"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
      'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="m9 7-5 5 5 5M15 7l5 5-5 5"/></svg></span>';

    var arrastrando = false;
    function desde(ev) {
      var r = map.getContainer().getBoundingClientRect();
      var cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      colocarSwipe(cx / r.width);
    }
    function inicio(ev) { arrastrando = true; divHandle.classList.add("arrastrando"); desde(ev); ev.preventDefault(); }
    function mueve(ev) { if (arrastrando) desde(ev); }
    function fin() { arrastrando = false; divHandle.classList.remove("arrastrando"); }

    divHandle.addEventListener("mousedown", inicio);
    divHandle.addEventListener("touchstart", inicio, { passive: false });
    window.addEventListener("mousemove", mueve);
    window.addEventListener("touchmove", mueve, { passive: false });
    window.addEventListener("mouseup", fin);
    window.addEventListener("touchend", fin);

    L.DomEvent.disableClickPropagation(divHandle);
  }

  /* ------------------------------------------------------ huellas / IA */

  function estiloHuella(f) {
    var c = (CLASES[f.properties.cat] || CLASES.otro).color;
    return {
      color: c,
      weight: 1.2,
      opacity: 0.95,
      fillColor: c,
      fillOpacity: 0.28,
      /* la visibilidad real la gobierna el CSS con la clase .vista, para no
         pelear con los estilos inline de Leaflet durante el revelado */
      className: "huella huella--" + f.properties.cat,
    };
  }

  function cargarHuellas() {
    capaHuellas = L.geoJSON(datos, {
      pane: "huellas",
      style: estiloHuella,
      onEachFeature: function (f, capa) {
        capa.on("click", function (e) {
          L.DomEvent.stopPropagation(e);
          var p = f.properties;
          var cls = CLASES[p.cat] || CLASES.otro;
          SP.ficha.mostrar(p.nombre || "Edificación nueva", cls.etiqueta, [
            ["Huella", SP.entero(p.area_m2) + " m²"],
            ["Pisos", p.niveles ? String(p.niveles) : "—"],
            ["Categoría", cls.etiqueta],
            ["En 2014 aquí había", SUELO_2014[p.suelo_2014] || "—"],
          ]);
        });
      },
    }).addTo(map);
  }

  /* Revela las edificaciones en oleadas, de mayor a menor (ya vienen
     ordenadas por área), como si el modelo las fuera encontrando. */
  function escanear() {
    if (!capaHuellas) return;
    document.querySelector(".scanline").classList.remove("activa");
    /* reflow para reiniciar la animación */
    void document.querySelector(".scanline").offsetWidth;
    document.querySelector(".scanline").classList.add("activa");

    var capas = capaHuellas.getLayers();
    capas.forEach(function (c) { if (c._path) c._path.classList.remove("vista", "huella--pop"); });

    var i = 0, lote = 12;
    (function oleada() {
      for (var n = 0; n < lote && i < capas.length; n++, i++) {
        var p = capas[i]._path;
        if (!p) continue;
        p.classList.add("vista");
        void p.offsetWidth;        /* reinicia el destello neón */
        p.classList.add("huella--pop");
      }
      if (i < capas.length) setTimeout(oleada, 45);
    })();
  }

  /* -------------------------------------------------------------- modos */

  function aplicarModo(modo) {
    var comparar = modo === "comparar";
    paneDespues.style.transition = "none";
    if (comparar) {
      colocarSwipe(handleX < 0.95 && handleX > 0.05 ? handleX : 0.5);
      divHandle.style.display = "";
      document.querySelector(".epoca--antes").style.display = "";
      document.querySelector(".epoca--hoy").style.display = "";
    } else {
      /* solo detección: se muestra la imagen de hoy completa */
      paneDespues.style.clip = "auto";
      divHandle.style.display = "none";
      document.querySelector(".epoca--antes").style.display = "none";
      document.querySelector(".epoca--hoy").style.display = "none";
    }
  }

  /* ------------------------------------------------------------ leyenda */

  function pintarLeyenda() {
    var cont = document.getElementById("leyenda");
    var cuenta = {};
    datos.features.forEach(function (f) {
      cuenta[f.properties.cat] = (cuenta[f.properties.cat] || 0) + 1;
    });
    cont.innerHTML = "";
    Object.keys(CLASES).forEach(function (k) {
      if (!cuenta[k]) return;
      var fila = document.createElement("div");
      fila.className = "geoai-leyenda__item";
      var sw = document.createElement("span");
      sw.className = "geoai-leyenda__sw";
      sw.style.background = CLASES[k].color;
      var tx = document.createElement("span");
      tx.className = "geoai-leyenda__tx";
      tx.textContent = CLASES[k].etiqueta;
      var n = document.createElement("span");
      n.className = "geoai-leyenda__n sp-mono";
      n.textContent = cuenta[k];
      fila.appendChild(sw); fila.appendChild(tx); fila.appendChild(n);
      cont.appendChild(fila);
    });
  }

  /* ------------------------------------------------------------ arranque */

  window.addEventListener("DOMContentLoaded", function () {
    SP.cargarJSON(DATOS).then(function (fc) {
      datos = fc;
      iniciarMapa();
    }).catch(function (e) {
      SP.listo();
      SP.aviso("No se pudieron cargar las edificaciones: " + e.message);
    });

    setTimeout(SP.listo, 20000);
  });

  function iniciarMapa() {
    var incrustado = window.self !== window.top;

    map = L.map("map", {
      center: CENTRO,
      zoom: 16,
      minZoom: 13,
      maxZoom: 19,
      zoomControl: false,
      attributionControl: false,
      scrollWheelZoom: !incrustado,
    });
    window.spMap = map;

    map.createPane("antes");
    map.createPane("despues");
    map.createPane("huellas");
    map.getPane("antes").style.zIndex = 200;
    map.getPane("despues").style.zIndex = 300;
    map.getPane("huellas").style.zIndex = 400;
    paneDespues = map.getPane("despues");

    /* La imagen Wayback de 2014 solo tiene teselas hasta z17 en esta zona; con
       maxNativeZoom:17 Leaflet amplía la mejor que hay al acercar (algo borrosa,
       pero es la resolución real de 2014) en vez de pedir z18+ y quedar en negro. */
    L.tileLayer(TESELAS_2014, { pane: "antes", maxNativeZoom: 17, maxZoom: 19 }).addTo(map);
    L.tileLayer(TESELAS_HOY, { pane: "despues", maxNativeZoom: 19, maxZoom: 19 }).addTo(map);

    L.control.zoom({ position: "topright" }).addTo(map);
    L.control.scale({ position: "bottomright", imperial: false, maxWidth: 110 }).addTo(map);

    crearHandle();
    colocarSwipe(0.5);
    cargarHuellas();
    pintarLeyenda();

    map.on("mousemove", function (e) { SP.coordenadas(e.latlng.lng, e.latlng.lat); });
    map.on("click", function () { SP.ficha.cerrar(); });
    map.on("move", function () { colocarSwipe(handleX); });

    /* el tamaño del mapa ya está; lanzamos el espectáculo */
    SP.listo();
    lanzarContadores();
    setTimeout(escanear, 500);

    enlazarControles();
  }

  function enlazarControles() {
    document.getElementById("reescanear").addEventListener("click", function () {
      lanzarContadores();
      escanear();
    });

    document.getElementById("mostrar-huellas").addEventListener("change", function () {
      if (this.checked) { map.addLayer(capaHuellas); escanear(); }
      else map.removeLayer(capaHuellas);
    });

    document.querySelectorAll("[data-modo-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll("[data-modo-btn]").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b === btn));
        });
        aplicarModo(btn.dataset.modoBtn);
      });
    });
  }
})();
