"""Smoke tests — run against the running server via httpx."""

import os

import httpx
import pytest


BASE = os.environ.get("WINE_TEST_URL", "http://localhost:8002")


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

    def test_groups_page(self):
        resp = httpx.get(f"{BASE}/groups")
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

    def test_personal_feed_no_auth(self):
        resp = httpx.get(f"{BASE}/api/feed/personal")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 0  # No auth = no personal feed

    def test_follow_status(self):
        resp = httpx.get(f"{BASE}/api/follow/wine_lover/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "following" in data

    def test_follow_counts(self):
        resp = httpx.get(f"{BASE}/api/follows/wine_lover")
        assert resp.status_code == 200
        data = resp.json()
        assert "following_count" in data

    def test_groups_api(self):
        resp = httpx.get(f"{BASE}/api/groups")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data

    def test_locations_nearby(self):
        resp = httpx.get(f"{BASE}/api/locations/nearby?lat=38.4&lon=-122.4&radius=500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"

    def test_wine_detail(self):
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
        import random
        suffix = random.randint(10000, 99999)
        client = httpx.Client()
        resp = client.post(f"{BASE}/api/auth/register", data={
            "username": f"testuser_{suffix}",
            "email": f"test_{suffix}@test.com",
            "password": "testpass123"
        })
        assert resp.status_code in (200, 303), f"Register failed: {resp.status_code}"

        resp = client.get(BASE)
        assert resp.status_code == 200

        resp = client.post(f"{BASE}/api/auth/logout")
        assert resp.status_code in (200, 303)

        resp = client.post(f"{BASE}/api/auth/login", data={
            "email": f"test_{suffix}@test.com",
            "password": "testpass123"
        })
        assert resp.status_code in (200, 303)

    def test_404_handling(self):
        resp = httpx.get(f"{BASE}/profile/nonexistent_user_xyz")
        assert resp.status_code == 404

    # ── Phase 3 tests ─────────────────────────────────────────────────

    def test_taste_profile(self):
        resp = httpx.get(f"{BASE}/api/profile/wine_lover/taste")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_data"] is True
        assert data["total_tastings"] > 0
        assert "favorite_type" in data

    def test_recommendations(self):
        resp = httpx.get(f"{BASE}/api/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_heatmap(self):
        resp = httpx.get(f"{BASE}/api/locations/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data

    def test_heatmap_filtered(self):
        resp = httpx.get(f"{BASE}/api/locations/heatmap?wine_type=red")
        assert resp.status_code == 200

    def test_dashboard_page(self):
        resp = httpx.get(f"{BASE}/dashboard")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text or "Your Palate" in resp.text

    def test_export_csv_no_auth(self):
        resp = httpx.get(f"{BASE}/api/wines/export")
        assert resp.status_code == 401