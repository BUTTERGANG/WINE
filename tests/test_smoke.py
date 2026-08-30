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
        resp = httpx.get(f"{BASE}/wine/{wine_id}")
        assert resp.status_code == 200
        assert "Margaux" in resp.text
        # legacy URL still redirects
        resp = httpx.get(f"{BASE}/api/wines/{wine_id}", follow_redirects=True)
        assert resp.status_code == 200

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

    # ── Regression tests for the functionality/design pass ────────────

    def _authed_client(self):
        import random
        suffix = random.randint(100000, 999999)
        client = httpx.Client(base_url=BASE, follow_redirects=True)
        r = client.post("/api/auth/register", data={
            "username": f"qa_{suffix}", "email": f"qa_{suffix}@t.com", "password": "testpass123",
        })
        assert r.status_code == 200
        return client, f"qa_{suffix}"

    def test_unchecked_is_public_stays_private(self):
        client, uname = self._authed_client()
        r = client.post("/api/wines", data={
            "producer": "Regression Cellars", "name": f"Private Pour {uname}",
            "wine_type": "red", "rating": "4", "notes": "should not be public",
            # is_public intentionally omitted
        })
        assert r.status_code == 200
        wine_id = r.json()["wine_id"]
        feed = httpx.get(f"{BASE}/api/feed?limit=50").json()["items"]
        assert all(i["wine_id"] != wine_id for i in feed), "private note leaked into public feed"

    def test_follow_unknown_user_is_404_not_500(self):
        client, _ = self._authed_client()
        r = client.post("/api/follow/definitely-not-a-real-user")
        assert r.status_code == 404

    def test_follow_by_username_roundtrips(self):
        client, _ = self._authed_client()
        r = client.post("/api/follow/sommelier_sam")
        assert r.status_code == 200 and r.json()["following"] is True
        r = client.post("/api/follow/sommelier_sam")
        assert r.status_code == 200 and r.json()["following"] is False

    def test_create_group_returns_group_list(self):
        client, uname = self._authed_client()
        r = client.post("/api/groups", data={"name": f"QA Group {uname}"})
        assert r.status_code == 200
        body = r.json()
        assert "groups" in body and any(g["name"] == f"QA Group {uname}" for g in body["groups"])

    def test_add_wine_returns_json_not_page(self):
        client, uname = self._authed_client()
        r = client.post("/api/wines", data={
            "producer": "JSON Test", "name": uname, "wine_type": "white", "rating": "3",
        })
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_add_wine_rejects_bad_vintage(self):
        client, uname = self._authed_client()
        r = client.post("/api/wines", data={
            "producer": "Bad Vintage", "name": uname, "wine_type": "red",
            "rating": "3", "vintage": "not-a-year",
        })
        assert r.status_code == 400

    def test_sessions_survive_via_signed_cookie(self):
        client, _ = self._authed_client()
        # a fresh client carrying only the cookie value should still be logged in
        token = client.cookies.get("session_token")
        assert token
        c2 = httpx.Client(base_url=BASE, cookies={"session_token": token}, follow_redirects=True)
        r = c2.get("/api/recommendations")
        assert r.status_code == 200

    def test_csv_export_escapes_formula_injection(self):
        client, uname = self._authed_client()
        client.post("/api/wines", data={
            "producer": "Inject", "name": uname, "wine_type": "red", "rating": "5",
            "notes": "=cmd|/c calc", "is_public": "1",
        })
        r = client.get("/api/wines/export")
        assert r.status_code == 200
        assert "\n'=cmd" in r.text or ",'=cmd" in r.text

    def test_quick_log_name_only(self):
        client, uname = self._authed_client()
        r = client.post("/api/wines", data={"name": f"House Red {uname}", "rating": "4"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_log_requires_a_rating(self):
        client, uname = self._authed_client()
        r = client.post("/api/wines", data={"name": f"Unrated {uname}"})
        assert r.status_code == 400

    def test_log_requires_a_wine(self):
        client, _ = self._authed_client()
        r = client.post("/api/wines", data={"rating": "3"})
        assert r.status_code == 400

    def test_recent_wines_endpoint(self):
        client, uname = self._authed_client()
        client.post("/api/wines", data={"name": f"Recent {uname}", "rating": "5"})
        r = client.get("/api/wines/mine/recent")
        assert r.status_code == 200
        wines = r.json()["wines"]
        assert any(w["name"] == f"Recent {uname}" for w in wines)

    def test_reverse_geocode_shape(self):
        r = httpx.post(f"{BASE}/api/locations/reverse", data={"lat": 48.8566, "lon": 2.3522})
        assert r.status_code == 200
        body = r.json()
        assert "name" in body and "venue_type" in body

    def test_group_detail_new_url(self):
        client, uname = self._authed_client()
        gid = client.post("/api/groups", data={"name": f"URL Group {uname}"}).json()["id"]
        r = httpx.get(f"{BASE}/group/{gid}")
        assert r.status_code == 200 and "URL Group" in r.text