"""Smoke tests — run against the running server via httpx."""

import httpx
import pytest
import asyncio


BASE = "http://localhost:8002"


class TestSmoke:
    """Run against a running server instance."""

    def test_health(self):
        resp = httpx.get(f"{BASE}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_landing_page(self):
        resp = httpx.get(BASE)
        assert resp.status_code == 200
        assert "WINE" in resp.text

    def test_login_page(self):
        resp = httpx.get(f"{BASE}/api/auth/login")
        assert resp.status_code == 200

    def test_register_page(self):
        resp = httpx.get(f"{BASE}/api/auth/register")
        assert resp.status_code == 200

    def test_map_page(self):
        resp = httpx.get(f"{BASE}/map")
        assert resp.status_code == 200

    def test_add_wine_page(self):
        resp = httpx.get(f"{BASE}/wine/add")
        assert resp.status_code == 200

    def test_scan_page(self):
        resp = httpx.get(f"{BASE}/wine/scan")
        assert resp.status_code == 200

    def test_feed_page(self):
        resp = httpx.get(f"{BASE}/feed")
        assert resp.status_code == 200

    def test_search_api(self):
        resp = httpx.get(f"{BASE}/api/wines/search?q=Cabernet")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0

    def test_feed_api(self):
        resp = httpx.get(f"{BASE}/api/feed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

    def test_locations_nearby(self):
        resp = httpx.get(f"{BASE}/api/locations/nearby?lat=38.4&lon=-122.4&radius=500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"

    def test_wine_detail(self):
        # Get a wine from search first
        resp = httpx.get(f"{BASE}/api/wines/search?q=Margaux")
        data = resp.json()
        assert len(data["results"]) > 0
        wine_id = data["results"][0]["id"]
        resp = httpx.get(f"{BASE}/api/wines/{wine_id}")
        assert resp.status_code == 200
        assert "Margaux" in resp.text

    def test_wine_reviews(self):
        resp = httpx.get(f"{BASE}/api/wines/search?q=Margaux")
        data = resp.json()
        wine_id = data["results"][0]["id"]
        resp = httpx.get(f"{BASE}/api/wines/{wine_id}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_profile_lookup(self):
        resp = httpx.get(f"{BASE}/profile/wine_lover")
        assert resp.status_code == 200

    def test_register_and_auth(self):
        """Test the full auth cycle."""
        client = httpx.Client()
        # Register
        resp = client.post(f"{BASE}/api/auth/register", data={
            "username": "smoke_test_user",
            "email": "smoke@test.com",
            "password": "testpass123"
        })
        assert resp.status_code == 303 or resp.status_code == 200

        # Try authenticated page
        resp = client.get(BASE)
        assert resp.status_code == 200

        # Logout
        resp = client.post(f"{BASE}/api/auth/logout")
        assert resp.status_code == 303 or resp.status_code == 200

        # Login
        resp = client.post(f"{BASE}/api/auth/login", data={
            "email": "smoke@test.com",
            "password": "testpass123"
        })
        assert resp.status_code == 303 or resp.status_code == 200

    def test_404_handling(self):
        resp = httpx.get(f"{BASE}/profile/nonexistent_user_xyz")
        assert resp.status_code == 404