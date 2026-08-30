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

    # ── Winery tests ─────────────────────────────────────────────────

    def test_wineries_page(self):
        resp = httpx.get(f"{BASE}/wineries")
        assert resp.status_code == 200

    def test_winery_search(self):
        resp = httpx.get(f"{BASE}/api/wineries/search?q=Napa")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_winery_search_specific(self):
        resp = httpx.get(f"{BASE}/api/wineries/search?q=Mondavi")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0
        assert "Mondavi" in data["results"][0]["name"]

    def test_winery_nearby(self):
        resp = httpx.get(f"{BASE}/api/wineries/nearby?lat=38.4&lon=-122.4&radius=200")
        assert resp.status_code == 200
        data = resp.json()
        assert "features" in data

    def test_winery_detail_lookup(self):
        resp = httpx.get(f"{BASE}/api/wineries/search?q=Mondavi")
        data = resp.json()
        if data["results"]:
            winery_id = data["results"][0].get("id")
            if winery_id:
                resp = httpx.get(f"{BASE}/venue/{winery_id}")
                assert resp.status_code == 200
                assert "Mondavi" in resp.text
                # legacy winery URL redirects to the venue page
                resp = httpx.get(f"{BASE}/api/wineries/{winery_id}", follow_redirects=True)
                assert resp.status_code == 200

    def test_venue_page_shows_wines_poured(self):
        # French Laundry (seed) has tastings
        r = httpx.get(f"{BASE}/api/feed?limit=50").json()["items"]
        loc = next((i for i in r if i.get("location_id")), None)
        if loc:
            resp = httpx.get(f"{BASE}/venue/{loc['location_id']}")
            assert resp.status_code == 200
            assert "Wines poured here" in resp.text

    def test_feed_items_carry_location_id(self):
        items = httpx.get(f"{BASE}/api/feed?limit=50").json()["items"]
        assert any("location_id" in i for i in items)

    def test_group_detail_page_restored(self):
        # /group/{id} was dropped during the winery merge — regression guard
        client, _ = self._authed()
        gid = client.post("/api/groups", data={"name": f"Grp {client.uname}"}).json()["id"]
        assert httpx.get(f"{BASE}/group/{gid}").status_code == 200

    # ── core behaviour guards (restored after the winery merge) ────────

    def _authed(self):
        import random
        s = random.randint(100000, 999999)
        c = httpx.Client(base_url=BASE, follow_redirects=True)
        r = c.post("/api/auth/register", data={"username": f"qa_{s}", "email": f"qa_{s}@t.com", "password": "testpass123"})
        assert r.status_code == 200
        c.uname = f"qa_{s}"
        return c, c.uname

    def test_add_wine_returns_json_and_quick_log(self):
        c, u = self._authed()
        r = c.post("/api/wines", data={"name": f"House White {u}", "rating": "4"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_log_requires_rating_and_wine(self):
        c, u = self._authed()
        assert c.post("/api/wines", data={"name": f"x{u}"}).status_code == 400
        assert c.post("/api/wines", data={"rating": "3"}).status_code == 400
        assert c.post("/api/wines", data={"name": f"y{u}", "rating": "3", "vintage": "nope"}).status_code == 400

    def test_unchecked_is_public_stays_private(self):
        c, u = self._authed()
        wid = c.post("/api/wines", data={"name": f"Private {u}", "rating": "5", "notes": "secret"}).json()["wine_id"]
        feed = httpx.get(f"{BASE}/api/feed?limit=50").json()["items"]
        assert all(i["wine_id"] != wid for i in feed)

    def test_follow_unknown_user_404_not_500(self):
        c, _ = self._authed()
        assert c.post("/api/follow/nope-not-real").status_code == 404

    def test_follow_by_username_roundtrips(self):
        c, _ = self._authed()
        assert c.post("/api/follow/sommelier_sam").json()["following"] is True
        assert c.post("/api/follow/sommelier_sam").json()["following"] is False

    def test_create_group_returns_list(self):
        c, u = self._authed()
        body = c.post("/api/groups", data={"name": f"QA {u}"}).json()
        assert any(g["name"] == f"QA {u}" for g in body.get("groups", []))

    def test_session_is_stateless_cookie(self):
        c, _ = self._authed()
        tok = c.cookies.get("session_token")
        c2 = httpx.Client(base_url=BASE, cookies={"session_token": tok})
        assert c2.get("/api/recommendations").status_code == 200

    def test_csv_export_escapes_formulas(self):
        c, u = self._authed()
        c.post("/api/wines", data={"name": f"Inj {u}", "rating": "5", "notes": "=1+1", "is_public": "1"})
        text = c.get("/api/wines/export").text
        assert "\n'=1+1" in text or ",'=1+1" in text

    def test_recent_wines_and_reverse_geocode(self):
        c, u = self._authed()
        c.post("/api/wines", data={"name": f"Recent {u}", "rating": "4"})
        assert any(w["name"] == f"Recent {u}" for w in c.get("/api/wines/mine/recent").json()["wines"])
        rg = httpx.post(f"{BASE}/api/locations/reverse", data={"lat": 48.8566, "lon": 2.3522})
        assert rg.status_code == 200 and "venue_type" in rg.json()