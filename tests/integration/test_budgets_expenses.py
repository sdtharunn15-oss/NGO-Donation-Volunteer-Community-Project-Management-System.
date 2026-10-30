from uuid import uuid4


def register_donor_and_login(client):
    email = f"budget_test_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Budget Test Donor",
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


def test_budget_requires_authentication(client):
    response = client.get("/budgets/")
    assert response.status_code == 401


def test_expense_requires_authentication(client):
    response = client.get("/expenses/")
    assert response.status_code == 401


def test_budget_rejects_missing_project(client):
    headers = register_donor_and_login(client)

    response = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": 999999999,
            "allocated_amount": "10000.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 403


def test_expense_rejects_missing_project(client):
    headers = register_donor_and_login(client)

    response = client.post(
        "/expenses/",
        headers=headers,
        json={
            "project_id": 999999999,
            "category": "Transport",
            "description": "Travel for project work",
            "amount": "500.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 403


def test_expense_validation_rejects_zero_amount(client):
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    email = f"finance_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    client.post(
        "/auth/register",
        json={
            "full_name": "Finance Test User",
            "email": email,
            "password": password,
        },
    )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.role = UserRole.FINANCE_OFFICER
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    response = client.post(
        "/expenses/",
        headers=headers,
        json={
            "project_id": 1,
            "category": "Transport",
            "description": "Travel for project work",
            "amount": "0",
            "currency": "INR",
        },
    )

    assert response.status_code == 422