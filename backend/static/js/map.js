// WINE — home page map (dense, dark, data-aware)
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var el = document.getElementById('home-map');
        if (!el || el.dataset.mapInit !== 'true' || typeof L === 'undefined') return;

        el.innerHTML = '';
        var map = L.map('home-map', {
            zoomControl: false,
            dragging: true,
            scrollWheelZoom: true,
            attributionControl: false,
        }).setView([38.5, -122.5], 10);

        // Dark tiles via CSS filter
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
        var style = document.createElement('style');
        style.textContent = '.leaflet-tile { filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7); }';
        document.head.appendChild(style);

        function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
        function stars(n) { return '★'.repeat(Math.min(Math.max(n|0,0),5)) + '☆'.repeat(Math.max(5-Math.min(Math.max(n|0,0),5),0)); }

        var allMarkers = [];
        var bounds = [];

        function addPin(lat, lon, color, popup) {
            var icon = L.divIcon({
                className: 'wine-pin',
                html: '<div style="background:' + color + '!important"></div>',
                iconSize: [14, 14],
                iconAnchor: [7, 14]
            });
            var marker = L.marker([lat, lon], { icon: icon }).bindPopup(popup);
            marker.addTo(map);
            allMarkers.push(marker);
            bounds.push([lat, lon]);
        }

        function loadWineries() {
            fetch('/api/wineries/nearby?lat=38.5&lon=-122&radius=500')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    (data.features || []).forEach(function (f) {
                        var c = f.geometry.coordinates, p = f.properties;
                        addPin(c[1], c[0], '#6b4e3a', '<b>🏘️ ' + esc(p.name) + '</b>' + (p.tasting_count ? '<br>🍷 ' + p.tasting_count + ' tastings' : ''));
                    });
                    fitBounds();
                })
                .catch(function () { fitBounds(); });
        }

        function loadTastings() {
            fetch('/api/locations/nearby?lat=38.5&lon=-122&radius=50000')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var features = data.features || [];
                    if (features.length < 10) {
                        // Not enough tastings, show wineries too
                        loadWineries();
                    } else {
                        features.forEach(function (f) {
                            var c = f.geometry.coordinates, p = f.properties;
                            addPin(c[1], c[0], '#b04116', 
                                '<b>' + esc(p.wine_name) + '</b><br>' +
                                stars(p.rating) + '<br>by ' + esc(p.username) +
                                '<br><a href="/wine/' + esc(p.wine_id) + '" style="color:#e98844">View →</a>'
                            );
                        });
                        fitBounds();
                    }
                })
                .catch(function () { loadWineries(); });
        }

        function fitBounds() {
            if (bounds.length > 1) {
                map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
            } else if (bounds.length === 1) {
                map.setView(bounds[0], 10);
            }
        }

        // Try user's location first
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function (pos) {
                var ll = [pos.coords.latitude, pos.coords.longitude];
                addPin(ll[0], ll[1], '#e98844', 'You');
                map.setView(ll, 9);
                loadTastings();
            }, function () { loadTastings(); });
        } else {
            loadTastings();
        }
    });
})();
