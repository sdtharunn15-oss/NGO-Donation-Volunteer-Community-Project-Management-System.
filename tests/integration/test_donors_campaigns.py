from uuid import uuid4


def register_and_login_donor(client):
    email = f"donor_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    register_response = client.post(
        "/auth/register",
        json={
            "full_name": "Integration Test Donor",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    return {
        "Authorization": f"Bearer {access_token}"
    }


def test_donor_profile_requires_authentication(client):
    response = client.get("/donors/me")
    assert response.status_code == 401


def test_campaign_list_is_accessible(client):
    response = client.get("/campaigns/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_donor_can_create_profile(client):
    headers = register_and_login_donor(client)

    response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "address": "Test Street",
            "city": "Chennai",
        },
    )

    assert response.status_code in (200, 201)
    data = response.json()
    assert "id" in data


def test_donor_can_view_own_profile(client):
    headers = register_and_login_donor(client)

    create_response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543211",
            "address": "Test Street",
            "city": "Chennai",
        },
    )
    assert create_response.status_code in (200, 201)

    response = client.get("/donors/me", headers=headers)
    assert response.status_code == 200


def test_donor_cannot_create_duplicate_profile(client):
    headers = register_and_login_donor(client)
    payload = {
        "phone": "9876543212",
        "address": "First Street",
        "city": "Chennai",
    }

    first = client.post("/donors/me", headers=headers, json=payload)
    assert first.status_code == 201

    second = client.post("/donors/me", headers=headers, json=payload)
    assert second.status_code == 409


def test_donor_can_update_own_profile(client):
    headers = register_and_login_donor(client)

    create_response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543213",
            "address": "Old Street",
            "city": "Chennai",
        },
    )
    assert create_response.status_code == 201

    response = client.patch(
        "/donors/me",
        headers=headers,
        json={
            "address": "New Street",
            "city": "Thiruvallur",
        },
    )

    assert response.status_code == 200
    assert response.json()["address"] == "New Street"
    assert response.json()["city"] == "Thiruvallur"


def test_donor_profile_not_found_before_creation(client):
    headers = register_and_login_donor(client)

    response = client.get("/donors/me", headers=headers)

    assert response.status_code == 404


def test_donor_cannot_list_all_donors(client):
    headers = register_and_login_donor(client)

    response = client.get("/donors/", headers=headers)

    assert response.status_code == 403


def test_donor_profile_creation_rejects_invalid_phone(client):
    headers = register_and_login_donor(client)

    response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "",
            "address": "Test Street",
            "city": "Chennai",
        },
    )

    assert response.status_code == 422

def test_donor_cannot_create_duplicate_profile(client):
    headers = register_and_login_donor(client)
    payload = {
        "phone": "9876543212",
        "address": "First Street",
        "city": "Chennai",
    }

    first = client.post("/donors/me", headers=headers, json=payload)
    assert first.status_code == 201

    second = client.post("/donors/me", headers=headers, json=payload)
    assert second.status_code == 409


def test_donor_can_update_own_profile(client):
    headers = register_and_login_donor(client)

    create_response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543213",
            "address": "Old Street",
            "city": "Chennai",
        },
    )
    assert create_response.status_code == 201

    response = client.patch(
        "/donors/me",
        headers=headers,
        json={
            "address": "New Street",
            "city": "Thiruvallur",
        },
    )

    assert response.status_code == 200
    assert response.json()["address"] == "New Street"
    assert response.json()["city"] == "Thiruvallur"


def test_donor_profile_not_found_before_creation(client):
    headers = register_and_login_donor(client)

    response = client.get("/donors/me", headers=headers)

    assert response.status_code == 404


def test_donor_cannot_list_all_donors(client):
    headers = register_and_login_donor(client)

    response = client.get("/donors/", headers=headers)

    assert response.status_code == 403


def test_donor_profile_creation_rejects_invalid_phone(client):
    headers = register_and_login_donor(client)

    response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "",
            "address": "Test Street",
            "city": "Chennai",
        },
    )

    assert response.status_code == 422
