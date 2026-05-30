"""Backend tests for Donas painel admin.

Cobre:
  - Tracking endpoints (público) - access, registration, pix-generated/copied/downloaded
  - Admin auth - login OK/erro, /me, Bearer token
  - Dashboard endpoints (KPIs, funnel, locations, activity, realtime, access-list, reset)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opa-amor.preview.emergentagent.com").rstrip("/")
ADMIN_USER = "donas"
ADMIN_PASS = "Seinao10@@"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_headers(api):
    # Reset before login to start clean state for KPI tests
    r = api.post(f"{BASE_URL}/api/admin/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Clear data once at start
    requests.post(f"{BASE_URL}/api/admin/dashboard/reset-kpis", headers=headers)
    return headers


# --- Health/root ---
class TestRoot:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        assert r.json().get("ok") is True


# --- Admin auth ---
class TestAdminAuth:
    def test_login_success(self, api):
        r = api.post(f"{BASE_URL}/api/admin/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200
        body = r.json()
        assert "token" in body and isinstance(body["token"], str) and len(body["token"]) > 10
        assert body["user"]["username"] == ADMIN_USER
        assert body["user"]["role"] == "admin"
        # cookie set
        assert "admin_token" in r.cookies

    def test_login_bad_password(self, api):
        r = api.post(f"{BASE_URL}/api/admin/auth/login", json={"username": ADMIN_USER, "password": "wrong"})
        assert r.status_code == 401

    def test_login_bad_user(self, api):
        r = api.post(f"{BASE_URL}/api/admin/auth/login", json={"username": "nope", "password": "x"})
        assert r.status_code == 401

    def test_me_without_token(self, api):
        r = requests.get(f"{BASE_URL}/api/admin/auth/me")
        assert r.status_code == 401

    def test_me_with_bearer(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/auth/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == ADMIN_USER
        assert body["role"] == "admin"


# --- Tracking (public) ---
class TestTracking:
    def test_track_access(self, api, auth_headers):
        # auth_headers fixture resets DB first
        r = api.post(f"{BASE_URL}/api/track/access", json={"page": "/home.html", "referrer": "test"})
        assert r.status_code == 200
        body = r.json()
        assert "id" in body
        assert body["page"] == "/home.html"
        assert "device" in body
        assert "city" in body

    def test_track_registration(self, api):
        r = api.post(f"{BASE_URL}/api/track/registration", json={
            "name": "TEST_Joao", "email": "t@t.com", "cpf": "12345678900", "phone": "11999"
        })
        assert r.status_code == 200
        body = r.json()
        assert "id" in body
        assert body["name"] == "TEST_Joao"

    def test_track_pix_generated(self, api):
        r = api.post(f"{BASE_URL}/api/track/pix-generated", json={
            "candidate_name": "TEST_Joao", "pix_code": "00020126...", "amount": 50.0
        })
        assert r.status_code == 200
        body = r.json()
        assert body["amount"] == 50.0

    def test_track_pix_copied(self, api):
        r = api.post(f"{BASE_URL}/api/track/pix-copied", json={
            "candidate_name": "TEST_Joao", "amount": 50.0
        })
        assert r.status_code == 200

    def test_track_pix_downloaded(self, api):
        r = api.post(f"{BASE_URL}/api/track/pix-downloaded", json={
            "candidate_name": "TEST_Joao", "amount": 50.0
        })
        assert r.status_code == 200


# --- Dashboard ---
class TestDashboard:
    def test_kpis_unauth(self):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/kpis")
        assert r.status_code == 401

    def test_kpis_reflect_tracking(self, auth_headers, api):
        # Seed deterministic data (auth_headers already reset DB)
        api.post(f"{BASE_URL}/api/track/access", json={"page": "/home.html"})
        api.post(f"{BASE_URL}/api/track/access", json={"page": "/cadastro.html"})
        api.post(f"{BASE_URL}/api/track/registration", json={"name": "TEST_A", "cpf": "1"})
        api.post(f"{BASE_URL}/api/track/pix-generated", json={"candidate_name": "TEST_A", "amount": 60.0})
        api.post(f"{BASE_URL}/api/track/pix-copied", json={"candidate_name": "TEST_A", "amount": 60.0})
        api.post(f"{BASE_URL}/api/track/pix-downloaded", json={"candidate_name": "TEST_A", "amount": 60.0})

        r = requests.get(f"{BASE_URL}/api/admin/dashboard/kpis", headers=auth_headers)
        assert r.status_code == 200
        k = r.json()
        # Verify keys present
        for key in ["acessos", "total_inscricoes", "valor_total_gerado",
                    "pix_gerados_count", "valor_pix_copiados", "pix_copiados_count",
                    "valor_pix_baixados", "pix_baixados_count"]:
            assert key in k, f"missing key {key}"
        assert k["acessos"] >= 2
        assert k["total_inscricoes"] >= 1
        assert k["pix_gerados_count"] >= 1
        assert k["valor_total_gerado"] >= 60.0
        assert k["pix_copiados_count"] >= 1
        assert k["pix_baixados_count"] >= 1

    def test_funnel(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/funnel", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "steps" in body and len(body["steps"]) == 5
        assert "rates" in body
        for k in ["insc_to_pix", "pix_to_baixados", "geral"]:
            assert k in body["rates"]

    def test_locations(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/locations", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)

    def test_activity_7days(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/activity-7days", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["labels"]) == 7
        assert len(body["acessos"]) == 7
        assert len(body["inscricoes"]) == 7

    def test_realtime(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/realtime", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)
        # At least the events from tracking should appear
        assert len(body["items"]) >= 1

    def test_access_list(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/access-list", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "total" in body

    def test_access_list_query(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/access-list?q=Desconhecida", headers=auth_headers)
        assert r.status_code == 200
        assert "items" in r.json()

    def test_reset_kpis(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/admin/dashboard/reset-kpis", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # Verify
        k = requests.get(f"{BASE_URL}/api/admin/dashboard/kpis", headers=auth_headers).json()
        assert k["acessos"] == 0
        assert k["total_inscricoes"] == 0
        assert k["pix_gerados_count"] == 0
