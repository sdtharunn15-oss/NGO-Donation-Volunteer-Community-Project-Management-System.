from uuid import uuid4


def create_user_and_login(client, role="donor"):
    email = f"{role}_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Donation Test User",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code in (200, 201)

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def test_donation_requires_authentication(client):
    response = client.post(
        "/donations/",
        json={"campaign_id": 1, "amount": 100, "currency": "INR"},
    )
    assert response.status_code == 401


def test_donation_requires_donor_profile(client):
    headers = create_user_and_login(client)

    response = client.post(
        "/donations/",
        headers=headers,
        json={"campaign_id": 1, "amount": 100, "currency": "INR"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Create your donor profile before donating"
    )


def test_donation_rejects_missing_campaign(client):
    headers = create_user_and_login(client)

    profile = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "address": "Test Street",
            "city": "Chennai",
        },
    )
    assert profile.status_code in (200, 201)

    response = client.post(
        "/donations/",
        headers=headers,
        json={
            "campaign_id": 999999999,
            "amount": 100,
            "currency": "INR",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Active campaign not found"


def test_campaign_creation_requires_staff_role(client):
    headers = create_user_and_login(client)

    response = client.post(
        "/campaigns/",
        headers=headers,
        json={
            "title": "Community Food Drive",
            "description": "Food support for local families",
            "goal_amount": 50000,
        },
    )

    assert response.status_code == 403


def create_staff_headers(client, role="super_admin"):
    from uuid import uuid4

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    email = f"donation_staff_{uuid4().hex[:10]}@example.com"
    db = SessionLocal()
    try:
        user = User(
            full_name="Donation Staff",
            email=email,
            hashed_password=hash_password("StrongPass123!"),
            role=UserRole(role),
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_active_campaign(client):
    headers = create_staff_headers(client)
    create_response = client.post(
        "/campaigns/",
        headers=headers,
        json={
            "title": "Donation Test Campaign",
            "description": "Campaign for donation integration tests",
            "goal_amount": 100000,
        },
    )
    assert create_response.status_code == 201
    campaign_id = create_response.json()["id"]

    activate_response = client.patch(
        f"/campaigns/{campaign_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert activate_response.status_code == 200
    return campaign_id


def create_donor_with_profile(client):
    headers = create_user_and_login(client)

    profile = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "address": "Donation Test Street",
            "city": "Chennai",
        },
    )
    assert profile.status_code == 201
    return headers


def test_donor_can_create_donation_for_active_campaign(client):
    headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    response = client.post(
        "/donations/",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "amount": "250.00",
            "currency": "inr",
            "message": "Support for the community",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["campaign_id"] == campaign_id
    assert data["amount"] == "250.00"
    assert data["currency"] == "INR"
    assert data["status"] == "pending"


def test_donation_rejects_zero_amount(client):
    headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    response = client.post(
        "/donations/",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "amount": 0,
            "currency": "INR",
        },
    )

    assert response.status_code == 422


def test_donation_rejects_negative_amount(client):
    headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    response = client.post(
        "/donations/",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "amount": -10,
            "currency": "INR",
        },
    )

    assert response.status_code == 422


def test_donor_can_view_own_donation_history(client):
    headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    create_response = client.post(
        "/donations/",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "amount": 500,
            "currency": "INR",
        },
    )
    assert create_response.status_code == 201

    response = client.get("/donations/me", headers=headers)

    assert response.status_code == 200
    assert any(
        item["id"] == create_response.json()["id"]
        for item in response.json()
    )


def test_donor_cannot_list_all_donations(client):
    headers = create_donor_with_profile(client)

    response = client.get("/donations/", headers=headers)

    assert response.status_code == 403


def test_finance_officer_can_complete_pending_donation(client):
    donor_headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    donation = client.post(
        "/donations/",
        headers=donor_headers,
        json={
            "campaign_id": campaign_id,
            "amount": 750,
            "currency": "INR",
        },
    )
    assert donation.status_code == 201

    finance_headers = create_staff_headers(client, "finance_officer")
    response = client.patch(
        f"/donations/{donation.json()['id']}/status",
        headers=finance_headers,
        params={"new_status": "completed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_donation_status_cannot_be_changed_twice(client):
    donor_headers = create_donor_with_profile(client)
    campaign_id = create_active_campaign(client)

    donation = client.post(
        "/donations/",
        headers=donor_headers,
        json={
            "campaign_id": campaign_id,
            "amount": 300,
            "currency": "INR",
        },
    )
    assert donation.status_code == 201

    finance_headers = create_staff_headers(client, "finance_officer")
    donation_id = donation.json()["id"]

    first = client.patch(
        f"/donations/{donation_id}/status",
        headers=finance_headers,
        params={"new_status": "completed"},
    )
    assert first.status_code == 200

    second = client.patch(
        f"/donations/{donation_id}/status",
        headers=finance_headers,
        params={"new_status": "failed"},
    )
    assert second.status_code == 409

