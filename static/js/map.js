/* CivicPulse Leaflet helpers. Tiles: OpenStreetMap (attribution required, light use only). */
(function () {
  const STATUS_COLORS = {
    REPORTED: "#64748b", UNDER_REVIEW: "#0284c7", ASSIGNED: "#7c3aed",
    IN_PROGRESS: "#d97706", RESOLVED: "#059669", REJECTED: "#dc2626",
  };

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function baseMap(el, center, zoom) {
    const map = L.map(el, { scrollWheelZoom: false }).setView(center, zoom);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    let failed = 0;
    tiles.on("tileerror", () => {
      failed += 1;
      const note = el.dataset.fallback && document.getElementById(el.dataset.fallback);
      if (failed >= 3 && note) note.hidden = false;
    });
    return map;
  }

  function center(el) {
    return [parseFloat(el.dataset.lat), parseFloat(el.dataset.lng)];
  }

  window.CivicMap = {
    STATUS_COLORS,

    /* Map of many issues loaded from a JSON endpoint. Returns { load(params) -> count }. */
    issues(el) {
      const map = baseMap(el, center(el), 13);
      const layer = L.layerGroup().addTo(map);
      async function load(params) {
        const res = await fetch(el.dataset.api + "?" + params, { headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        layer.clearLayers();
        const points = [];
        data.issues.forEach((i) => {
          const m = L.circleMarker([i.lat, i.lng], {
            radius: 8, color: "#ffffff", weight: 2, fillOpacity: 0.9,
            fillColor: STATUS_COLORS[i.status] || "#64748b",
          });
          m.bindPopup(
            `<strong>${esc(i.title)}</strong><br>` +
            `<span>${esc(i.code)} &middot; ${esc(i.status_label)}</span><br>` +
            `<span>${esc(i.category_label)}</span>` +
            (i.url ? `<br><a href="${esc(i.url)}">Open details</a>` : "")
          );
          m.addTo(layer);
          points.push([i.lat, i.lng]);
        });
        if (points.length) map.fitBounds(points, { padding: [30, 30], maxZoom: 15 });
        return points.length;
      }
      return { map, load };
    },

    /* Click or drag to set latitude/longitude inputs; typing in the inputs moves the pin. */
    picker(el, latInput, lngInput) {
      const hasValue = latInput.value && lngInput.value;
      const start = hasValue ? [parseFloat(latInput.value), parseFloat(lngInput.value)] : center(el);
      const map = baseMap(el, start, hasValue ? 16 : 13);
      let marker = null;
      function place(latlng, write) {
        if (!marker) {
          marker = L.marker(latlng, { draggable: true }).addTo(map);
          marker.on("dragend", () => place(marker.getLatLng(), true));
        } else {
          marker.setLatLng(latlng);
        }
        if (write) {
          latInput.value = latlng.lat.toFixed(6);
          lngInput.value = latlng.lng.toFixed(6);
          latInput.form && latInput.form.dispatchEvent(new Event("pin-moved", { bubbles: true }));
        }
      }
      if (hasValue) place(L.latLng(start), false);
      map.on("click", (e) => place(e.latlng, true));
      function fromInputs() {
        const lat = parseFloat(latInput.value), lng = parseFloat(lngInput.value);
        if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
          place(L.latLng(lat, lng), false);
          map.setView([lat, lng], Math.max(map.getZoom(), 15));
        }
      }
      latInput.addEventListener("change", fromInputs);
      lngInput.addEventListener("change", fromInputs);
      return { map, fromInputs };
    },

    /* One fixed pin, for the issue detail page. */
    single(el) {
      const map = baseMap(el, center(el), 16);
      L.marker(center(el)).addTo(map);
      return map;
    },
  };
})();
