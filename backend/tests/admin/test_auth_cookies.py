from fastapi.testclient import TestClient

from app.admin.deps import COOKIE_NAME, CSRF_COOKIE_NAME, _cookie_name


def _cookie_header(response, name: str) -> str:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header
    raise AssertionError(f"missing Set-Cookie for {name}")


def _attributes(header: str) -> list[str]:
    return [part.strip().lower() for part in header.split(";")[1:]]


def test_cookie_name_uses_host_prefix_only_when_deployed() -> None:
    assert _cookie_name("admin_csrf", deployed=True) == "__Host-admin_csrf"
    assert (
        _cookie_name("admin_access_token", deployed=True) == "__Host-admin_access_token"
    )
    assert _cookie_name("admin_csrf", deployed=False) == "admin_csrf"
    assert _cookie_name("admin_access_token", deployed=False) == "admin_access_token"


def test_csrf_cookie_is_host_scoped(client: TestClient) -> None:
    response = client.get("/login")
    header = _cookie_header(response, CSRF_COOKIE_NAME)
    attributes = _attributes(header)
    assert "path=/" in attributes
    assert not any(part.startswith("domain=") for part in attributes)


def test_logout_deletes_session_cookie(client: TestClient) -> None:
    client.get("/login")
    token = client.cookies[CSRF_COOKIE_NAME]
    response = client.post(
        "/logout",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    header = _cookie_header(response, COOKIE_NAME)
    attributes = _attributes(header)
    assert "max-age=0" in attributes
    assert "path=/" in attributes


def test_mismatched_csrf_is_forbidden(client: TestClient) -> None:
    client.get("/login")
    response = client.post(
        "/login",
        data={
            "email": "person@example.com",
            "password": "not-the-password",
            "csrf_token": "not-the-cookie",
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_profile_origin_is_not_allowed(client: TestClient) -> None:
    response = client.options(
        "/login",
        headers={"Origin": "https://profile.hvostun.com"},
    )
    assert "access-control-allow-origin" not in response.headers
