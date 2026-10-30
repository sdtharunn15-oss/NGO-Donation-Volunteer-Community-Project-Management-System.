
from uuid import uuid4

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_user_and_login(client, role="volunteer"):
    from uuid import uuid4
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    email = f"{role}_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Volunteer Test User",
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


def create_staff_headers(client, role="ngo_manager"):
    email = f"volunteer_staff_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Volunteer Test Staff",
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


def create_volunteer_profile(client, headers):
    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "skills": "Teaching, community service",
            "availability": "Weekends",
            "city": "Chennai",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_volunteer_profile_requires_authentication(client):
    response = client.post(
        "/volunteers/me",
        json={"skills": "Teaching"},
    )
    assert response.status_code == 401


def test_donor_cannot_create_volunteer_profile(client):
    headers = create_user_and_login(client, "donor")

    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={"skills": "Teaching"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Volunteer role required"


def test_volunteer_can_create_own_profile(client):
    headers = create_user_and_login(client)

    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "skills": "Teaching, first aid",
            "availability": "Weekends",
            "city": "Chennai",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] > 0
    assert data["phone"] == "9876543210"
    assert data["skills"] == "Teaching, first aid"
    assert data["availability"] == "Weekends"
    assert data["city"] == "Chennai"


def test_volunteer_cannot_create_duplicate_profile(client):
    headers = create_user_and_login(client)
    create_volunteer_profile(client, headers)

    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={"skills": "Another skill"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Profile already exists"


def test_volunteer_can_view_own_profile(client):
    headers = create_user_and_login(client)
    created = create_volunteer_profile(client, headers)

    response = client.get("/volunteers/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["user_id"] == created["user_id"]


def test_volunteer_profile_not_found(client):
    headers = create_user_and_login(client)

    response = client.get("/volunteers/me", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_volunteer_can_update_own_profile(client):
    headers = create_user_and_login(client)
    create_volunteer_profile(client, headers)

    response = client.patch(
        "/volunteers/me",
        headers=headers,
        json={
            "skills": "Teaching, first aid, event management",
            "availability": "Evenings",
            "city": "Thiruvallur",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["skills"] == "Teaching, first aid, event management"
    assert data["availability"] == "Evenings"
    assert data["city"] == "Thiruvallur"


def test_volunteer_cannot_update_missing_profile(client):
    headers = create_user_and_login(client)

    response = client.patch(
        "/volunteers/me",
        headers=headers,
        json={"city": "Chennai"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_volunteer_cannot_list_all_volunteers(client):
    headers = create_user_and_login(client)
    create_volunteer_profile(client, headers)

    response = client.get("/volunteers/", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_ngo_manager_can_list_volunteers(client):
    volunteer_headers = create_user_and_login(client)
    created = create_volunteer_profile(client, volunteer_headers)

    manager_headers = create_staff_headers(client, "ngo_manager")

    response = client.get("/volunteers/", headers=manager_headers)

    assert response.status_code == 200
    assert any(
        volunteer["id"] == created["id"]
        for volunteer in response.json()
    )


def test_volunteer_profile_rejects_oversized_phone(client):
    headers = create_user_and_login(client)

    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={"phone": "1" * 31},
    )

    assert response.status_code == 422
