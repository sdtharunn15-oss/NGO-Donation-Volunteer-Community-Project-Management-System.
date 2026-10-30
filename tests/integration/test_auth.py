from uuid import uuid4


def test_register_donor(client):
    email = f"test_donor_{uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test Donor",
            "email": email,
            "password": "StrongPass123!",
        },
    )

    assert response.status_code in (200, 201)
    data = response.json()
    assert data["email"] == email
    assert data["role"] == "donor"
    assert "hashed_password" not in data


def test_duplicate_registration_rejected(client):
    email = f"duplicate_{uuid4().hex[:10]}@example.com"
    payload = {
        "full_name": "Duplicate Donor",
        "email": email,
        "password": "StrongPass123!",
    }

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)

    assert first.status_code in (200, 201)
    assert second.status_code == 409


def test_protected_endpoint_requires_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_login_success_returns_access_and_refresh_tokens(client):
    email = f"login_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    register = client.post(
        "/auth/register",
        json={
            "full_name": "Login Test User",
            "email": email,
            "password": password,
        },
    )
    assert register.status_code in (200, 201)

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_login_rejects_wrong_password(client):
    email = f"wrongpass_{uuid4().hex[:10]}@example.com"

    client.post(
        "/auth/register",
        json={
            "full_name": "Wrong Password User",
            "email": email,
            "password": "StrongPass123!",
        },
    )

    response = client.post(
        "/auth/login",
        json={"email": email, "password": "WrongPass123!"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/auth/login",
        json={
            "email": f"unknown_{uuid4().hex[:10]}@example.com",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 401


def test_refresh_token_returns_new_tokens(client):
    email = f"refresh_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    client.post(
        "/auth/register",
        json={
            "full_name": "Refresh Test User",
            "email": email,
            "password": password,
        },
    )

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


def test_refresh_rejects_invalid_token(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.refresh.token"},
    )

    assert response.status_code == 401


def test_password_reset_unknown_email_returns_generic_response(client):
    response = client.post(
        "/auth/password-reset/request",
        json={"email": f"unknown_{uuid4().hex[:10]}@example.com"},
    )

    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json().get("reset_token") is None


def test_password_reset_changes_password_and_token_cannot_be_reused(
    client, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEBUG", True)

    email = f"reset_{uuid4().hex[:10]}@example.com"
    old_password = "OldPass123!"
    new_password = "NewPass123!"

    register = client.post(
        "/auth/register",
        json={
            "full_name": "Password Reset User",
            "email": email,
            "password": old_password,
        },
    )
    assert register.status_code in (200, 201)

    reset_request = client.post(
        "/auth/password-reset/request",
        json={"email": email},
    )
    assert reset_request.status_code == 200

    reset_token = reset_request.json().get("reset_token")
    assert reset_token

    reset_response = client.post(
        "/auth/password-reset/confirm",
        json={
            "reset_token": reset_token,
            "new_password": new_password,
        },
    )
    assert reset_response.status_code == 200

    old_login = client.post(
        "/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200

    reused_token = client.post(
        "/auth/password-reset/confirm",
        json={
            "reset_token": reset_token,
            "new_password": "AnotherPass123!",
        },
    )
    assert reused_token.status_code == 400


def test_password_reset_rejects_invalid_token(client):
    response = client.post(
        "/auth/password-reset/confirm",
        json={
            "reset_token": "not-a-valid-reset-token",
            "new_password": "NewPass123!",
        },
    )

    assert response.status_code == 400


def test_password_reset_rejects_short_new_password(client):
    response = client.post(
        "/auth/password-reset/confirm",
        json={
            "reset_token": "any-token",
            "new_password": "short",
        },
    )

    assert response.status_code == 422
