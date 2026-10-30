from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def create_user_and_login(client, role=UserRole.NGO_MANAGER):
    email = f"budget_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Budget Test Manager",
            email=email,
            hashed_password=hash_password(password),
            role=role,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_project(client, headers):
    response = client.post(
        "/projects/",
        headers=headers,
        json={
            "title": f"Budget Project {uuid4().hex[:8]}",
            "budget": "10000.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_budget_success(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    response = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "8000.00",
            "currency": "inr",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert float(data["allocated_amount"]) == 8000.00
    assert data["currency"] == "INR"


def test_duplicate_budget_rejected(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    payload = {
        "project_id": project["id"],
        "allocated_amount": "8000.00",
        "currency": "INR",
    }

    first = client.post("/budgets/", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    second = client.post("/budgets/", headers=headers, json=payload)
    assert second.status_code == 409, second.text


def test_list_budgets(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    created = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "5000.00",
            "currency": "INR",
        },
    )
    assert created.status_code == 201, created.text

    response = client.get("/budgets/", headers=headers)
    assert response.status_code == 200, response.text
    assert any(item["id"] == created.json()["id"] for item in response.json())


def test_get_budget_by_id(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    created = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "5000.00",
            "currency": "INR",
        },
    )
    assert created.status_code == 201, created.text

    budget_id = created.json()["id"]
    response = client.get(f"/budgets/{budget_id}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == budget_id


def test_update_budget_amount(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    created = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "5000.00",
            "currency": "INR",
        },
    )
    assert created.status_code == 201, created.text

    budget_id = created.json()["id"]
    response = client.patch(
        f"/budgets/{budget_id}",
        headers=headers,
        json={"allocated_amount": "7500.00"},
    )

    assert response.status_code == 200, response.text
    assert float(response.json()["allocated_amount"]) == 7500.00


def test_budget_not_found(client):
    headers = create_user_and_login(client)

    response = client.get("/budgets/999999999", headers=headers)
    assert response.status_code == 404


def test_budget_update_rejects_empty_payload(client):
    headers = create_user_and_login(client)
    project = create_project(client, headers)

    created = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "5000.00",
            "currency": "INR",
        },
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/budgets/{created.json()['id']}",
        headers=headers,
        json={},
    )
    assert response.status_code == 400, response.text
def create_staff_and_login(client, role):
    from uuid import uuid4

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    if isinstance(role, str):
        role = UserRole(role)

    email = f"expense_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Expense Test User",
            email=email,
            hashed_password=hash_password(password),
            role=role,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text

    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

def create_expense_project(client, headers):
    manager_headers = create_user_and_login(
        client,
        UserRole.NGO_MANAGER,
    )

    response = client.post(
        "/projects/",
        headers=manager_headers,
        json={
            "title": f"Expense Project {uuid4().hex[:8]}",
            "budget": "10000.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
def create_expense(client, headers, project_id, amount="500.00"):
    response = client.post(
        "/expenses/",
        headers=headers,
        json={
            "project_id": project_id,
            "category": "Transport",
            "description": "Travel for project work",
            "amount": amount,
            "currency": "INR",
            "receipt_reference": f"receipt-{uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_expense_success(client):
    headers = create_staff_and_login(client, "finance_officer")
    project = create_expense_project(client, headers)

    expense = create_expense(client, headers, project["id"])

    assert expense["project_id"] == project["id"]
    assert expense["status"] == "pending"
    assert expense["currency"] == "INR"
    assert expense["category"] == "Transport"


def test_my_expenses_returns_submitted_expenses(client):
    headers = create_staff_and_login(client, "volunteer_coordinator")
    project = create_expense_project(client, headers)

    created = create_expense(client, headers, project["id"])

    response = client.get("/expenses/me", headers=headers)

    assert response.status_code == 200, response.text
    assert any(item["id"] == created["id"] for item in response.json())


def test_list_expenses_filter_by_project(client):
    headers = create_staff_and_login(client, "finance_officer")
    project = create_expense_project(client, headers)

    created = create_expense(client, headers, project["id"])

    response = client.get(
        f"/expenses/?project_id={project['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert all(item["project_id"] == project["id"] for item in response.json())
    assert any(item["id"] == created["id"] for item in response.json())


def test_list_expenses_filter_by_status(client):
    headers = create_staff_and_login(client, "finance_officer")
    project = create_expense_project(client, headers)

    created = create_expense(client, headers, project["id"])

    response = client.get(
        "/expenses/?expense_status=pending",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert all(item["status"] == "pending" for item in response.json())
    assert any(item["id"] == created["id"] for item in response.json())


def test_get_expense_by_id(client):
    headers = create_staff_and_login(client, "finance_officer")
    project = create_expense_project(client, headers)

    created = create_expense(client, headers, project["id"])

    response = client.get(
        f"/expenses/{created['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]


def test_expense_not_found(client):
    headers = create_staff_and_login(client, "finance_officer")

    response = client.get("/expenses/999999999", headers=headers)

    assert response.status_code == 404


def test_approve_expense_success(client):
    submitter_headers = create_staff_and_login(client, "volunteer_coordinator")
    reviewer_headers = create_staff_and_login(client, "finance_officer")

    project = create_expense_project(client, submitter_headers)

    budget_response = client.post(
        "/budgets/",
        headers=reviewer_headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "10000.00",
            "currency": "INR",
        },
    )
    assert budget_response.status_code == 201, budget_response.text

    expense = create_expense(client, submitter_headers, project["id"])

    response = client.patch(
        f"/expenses/{expense['id']}/review",
        headers=reviewer_headers,
        json={
            "status": "approved",
            "review_notes": "Receipt verified",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["review_notes"] == "Receipt verified"


def test_reject_expense_success(client):
    submitter_headers = create_staff_and_login(client, "volunteer_coordinator")
    reviewer_headers = create_staff_and_login(client, "finance_officer")

    project = create_expense_project(client, submitter_headers)
    expense = create_expense(client, submitter_headers, project["id"])

    response = client.patch(
        f"/expenses/{expense['id']}/review",
        headers=reviewer_headers,
        json={
            "status": "rejected",
            "review_notes": "Insufficient documentation",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


def test_approval_requires_project_budget(client):
    submitter_headers = create_staff_and_login(client, "volunteer_coordinator")
    reviewer_headers = create_staff_and_login(client, "finance_officer")

    project = create_expense_project(client, submitter_headers)
    expense = create_expense(client, submitter_headers, project["id"])

    response = client.patch(
        f"/expenses/{expense['id']}/review",
        headers=reviewer_headers,
        json={"status": "approved"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Create a project budget before approving expenses"
    )


def test_expense_reviewer_cannot_review_own_expense(client):
    headers = create_staff_and_login(client, "finance_officer")
    project = create_expense_project(client, headers)

    budget_response = client.post(
        "/budgets/",
        headers=headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "10000.00",
            "currency": "INR",
        },
    )
    assert budget_response.status_code == 201, budget_response.text

    expense = create_expense(client, headers, project["id"])

    response = client.patch(
        f"/expenses/{expense['id']}/review",
        headers=headers,
        json={"status": "approved"},
    )

    assert response.status_code == 403


def test_approval_cannot_exceed_budget(client):
    submitter_headers = create_staff_and_login(client, "volunteer_coordinator")
    reviewer_headers = create_staff_and_login(client, "finance_officer")

    project = create_expense_project(client, submitter_headers)

    budget_response = client.post(
        "/budgets/",
        headers=reviewer_headers,
        json={
            "project_id": project["id"],
            "allocated_amount": "100.00",
            "currency": "INR",
        },
    )
    assert budget_response.status_code == 201, budget_response.text

    expense = create_expense(
        client,
        submitter_headers,
        project["id"],
        amount="500.00",
    )

    response = client.patch(
        f"/expenses/{expense['id']}/review",
        headers=reviewer_headers,
        json={"status": "approved"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Approving this expense would exceed the project budget"
    )