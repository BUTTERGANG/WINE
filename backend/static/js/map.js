// WINE — home page mini-map
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var el = document.getElementById('home-map');
        if (!el || el.dataset.mapInit !== 'true' || typeof L === 'undefined') return;

        el.innerHTML = '';
        var map = L.map('home-map', {
            zoomControl: false,
            dragging: false,
            scrollWheelZoom: false,
            attributionControl: false,
        }).setView([30, 0], 2);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);

        function loadPins(lat, lon, radius, zoom) {
            map.setView([lat, lon], zoom);
            fetch('/api/locations/nearby?lat=' + lat + '&lon=' + lon + '&radius=' + radius)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    (data.features || []).forEach(function (f) {
                        var c = f.geometry.coordinates, p = f.properties;
                        var icon = L.divIcon({ className: 'wine-pin', html: '<div></div>', iconSize: [20, 20], iconAnchor: [10, 20] });
                        L.marker([c[1], c[0]], { icon: icon })
                            .bindPopup('<b>' + esc(p.wine_name) + '</b><br>' + stars(p.rating))
                            .addTo(map);
                    });
                })
                .catch(function () {});
        }

        // Load a global view immediately; refine to the viewer's location if allowed.
        loadPins(20, 0, 20000, 2);
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function (pos) {
                loadPins(pos.coords.latitude, pos.coords.longitude, 500, 9);
            }, function () {});
        }
    });
})();
