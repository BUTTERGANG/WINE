// WINE map interactions
(function() {
    'use strict';

    // Init home page mini-map
    document.addEventListener('DOMContentLoaded', function() {
        const homeMap = document.getElementById('home-map');
        if (homeMap && homeMap.dataset.mapInit === 'true') {
            const center = [40, -95]; // US center default
            const map = L.map('home-map', {
                zoomControl: false,
                dragging: false,
                scrollWheelZoom: false,
                attributionControl: false,
            }).setView(center, 3);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {}).addTo(map);

            // Try user location
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function(pos) {
                    map.setView([pos.coords.latitude, pos.coords.longitude], 10);
                    // Fetch nearby pins
                    fetch(`/api/locations/nearby?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&radius=500`)
                        .then(r => r.json())
                        .then(data => {
                            (data.features || []).forEach(f => {
                                const coords = f.geometry.coordinates;
                                const p = f.properties;
                                const icon = L.divIcon({
                                    className: 'wine-pin',
                                    html: '<div></div>',
                                    iconSize: [20, 20],
                                    iconAnchor: [10, 20],
                                });
                                L.marker([coords[1], coords[0]], { icon })
                                    .bindPopup(`<b>${p.wine_name}</b><br>${'★'.repeat(p.rating)}`)
                                    .addTo(map);
                            });
                        });
                }, function() {
                    // Fallback: default center, no pins
                });
            }
        }
    });
})();