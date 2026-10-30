
from uuid import uuid4

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_user_and_login(client, role="donor"):
    email = f"{role}_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Receipt Test User",
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

    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_staff_headers(client, role="super_admin"):
    email = f"receipt_staff_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Receipt Staff",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole(role),
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_donor_with_profile(client):
    headers = create_user_and_login(client)

    response = client.post(
        "/donors/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "address": "Receipt Test Street",
            "city": "Chennai",
        },
    )
    assert response.status_code in (200, 201)

    return headers


def create_completed_donation(client, donor_headers=None):
    if donor_headers is None:
        donor_headers = create_donor_with_profile(client)

    staff_headers = create_staff_headers(client)

    campaign_response = client.post(
        "/campaigns/",
        headers=staff_headers,
        json={
            "title": f"Receipt Campaign {uuid4().hex[:6]}",
            "description": "Campaign for receipt tests",
            "goal_amount": 100000,
        },
    )
    assert campaign_response.status_code == 201
    campaign_id = campaign_response.json()["id"]

    activate_response = client.patch(
        f"/campaigns/{campaign_id}",
        headers=staff_headers,
        json={"status": "active"},
    )
    assert activate_response.status_code == 200

    donation_response = client.post(
        "/donations/",
        headers=donor_headers,
        json={
            "campaign_id": campaign_id,
            "amount": "500.00",
            "currency": "INR",
            "message": "Receipt integration test",
        },
    )
    assert donation_response.status_code == 201
    donation_id = donation_response.json()["id"]

    finance_headers = create_staff_headers(client, "finance_officer")
    complete_response = client.patch(
        f"/donations/{donation_id}/status",
        headers=finance_headers,
        params={"new_status": "completed"},
    )
    assert complete_response.status_code == 200

    return donation_id, donor_headers, finance_headers


def test_receipt_creation_requires_authentication(client):
    response = client.post("/receipts/donations/1")

    assert response.status_code == 401


def test_donor_cannot_create_receipt(client):
    donor_headers = create_donor_with_profile(client)

    response = client.post(
        "/receipts/donations/1",
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_receipt_rejects_missing_donation(client):
    finance_headers = create_staff_headers(client, "finance_officer")

    response = client.post(
        "/receipts/donations/999999999",
        headers=finance_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Donation not found"


def test_receipt_rejects_pending_donation(client):
    donor_headers = create_donor_with_profile(client)
    staff_headers = create_staff_headers(client)

    campaign_response = client.post(
        "/campaigns/",
        headers=staff_headers,
        json={
            "title": f"Pending Campaign {uuid4().hex[:6]}",
            "description": "Pending donation test",
            "goal_amount": 100000,
        },
    )
    assert campaign_response.status_code == 201
    campaign_id = campaign_response.json()["id"]

    activation = client.patch(
        f"/campaigns/{campaign_id}",
        headers=staff_headers,
        json={"status": "active"},
    )
    assert activation.status_code == 200

    donation = client.post(
        "/donations/",
        headers=donor_headers,
        json={
            "campaign_id": campaign_id,
            "amount": 100,
            "currency": "INR",
        },
    )
    assert donation.status_code == 201

    finance_headers = create_staff_headers(client, "finance_officer")
    response = client.post(
        f"/receipts/donations/{donation.json()['id']}",
        headers=finance_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Receipt can only be generated for completed donations"
    )


def test_finance_officer_can_create_receipt(client):
    donation_id, _, finance_headers = create_completed_donation(client)

    response = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["donation_id"] == donation_id
    assert data["receipt_number"].startswith(f"NGO-{donation_id:08d}-")
    assert data["id"] > 0
    assert data["issued_at"] is not None


def test_duplicate_receipt_is_rejected(client):
    donation_id, _, finance_headers = create_completed_donation(client)

    first = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )
    assert first.status_code == 201

    second = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )

    assert second.status_code == 409
    assert second.json()["detail"] == (
        "Receipt already exists for this donation"
    )


def test_donor_can_view_own_receipts(client):
    donation_id, donor_headers, finance_headers = create_completed_donation(client)

    created = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )
    assert created.status_code == 201

    response = client.get("/receipts/me", headers=donor_headers)

    assert response.status_code == 200
    assert any(
        item["id"] == created.json()["id"]
        for item in response.json()
    )


def test_donor_cannot_view_another_donors_receipt(client):
    donation_id, _, finance_headers = create_completed_donation(client)

    receipt = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )
    assert receipt.status_code == 201

    another_donor_headers = create_donor_with_profile(client)

    response = client.get(
        f"/receipts/{receipt.json()['id']}",
        headers=another_donor_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Receipt not found"


def test_finance_officer_can_view_receipt(client):
    donation_id, _, finance_headers = create_completed_donation(client)

    receipt = client.post(
        f"/receipts/donations/{donation_id}",
        headers=finance_headers,
    )
    assert receipt.status_code == 201

    response = client.get(
        f"/receipts/{receipt.json()['id']}",
        headers=finance_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == receipt.json()["id"]
