def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]


def test_invalid_login_rejected(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "missing.user@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code in (400, 401, 403, 422)
