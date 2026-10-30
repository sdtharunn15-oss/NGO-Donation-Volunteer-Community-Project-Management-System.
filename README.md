**NGO MANAGEMENT SYSTEM**

**Project Overview**

The NGO Management System is a backend application developed using FastAPI and Python. It is designed to simplify and manage the day-to-day operations of a Non-Governmental Organization (NGO).

The system provides APIs to manage users, beneficiaries, donors, donations, projects, volunteers, tasks, budgets, expenses, resources, campaigns, approvals, and other NGO-related activities.

It uses SQLAlchemy for database operations, SQLite as the default database, and Alembic for database schema migrations.

**Technologies Used**

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- Pydantic Settings
- JWT Authentication
- Password Hashing
- Alembic
- Pytest
- Uvicorn

**Main Modules**

1. User Management
   - User registration and login
   - Authentication and authorization
   - Role-based access control
   - Password reset functionality

2. Beneficiary Management
   - Create and manage beneficiaries
   - Maintain beneficiary information

3. Donor Management
   - Register and manage donors
   - Maintain donor records

4. Donation Management
   - Record donations
   - Track donation details
   - Generate donation receipts

5. Project Management
   - Create and manage NGO projects
   - Track project progress
   - Manage project milestones

6. Volunteer Management
   - Register and manage volunteers
   - Assign volunteers to projects

7. Task Management
   - Create and assign tasks
   - Track task status

8. Financial Management
   - Manage budgets
   - Record expenses
   - Track financial activities

9. Resource Management
   - Manage organizational resources
   - Allocate resources to projects

10. Campaign Management
    - Create and manage campaigns
    - Maintain campaign information

11. Approval Management
    - Manage approval requests
    - Track approval status

12. Notification Management
    - Maintain system notifications

13. Audit Log Management
    - Track important system activities
    - Maintain audit records

14. Impact Management
    - Record and manage project impact information

**Project Structure**

```text
ngo-management-system/
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── app/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── middleware/
│   ├── modules/
│   ├── main.py
│   └── ...
│
├── tests/
│
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
├── README.md
└── ngo_management.db
```

Note: The project structure above represents the main components. Actual subdirectories and files may vary depending on the implementation.

**Installation and Setup**

1. Clone or download the project.

2. Open the project directory:

```powershell
cd ngo-management-system
```

3. Create a virtual environment:

```powershell
python -m venv venv
```

4. Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

5. Install the required dependencies:

```powershell
pip install -r requirements.txt
```

**Environment Configuration**

Create a `.env` file in the project root directory and configure the required environment variables.

Example:

```env
APP_NAME=NGO Management System
APP_VERSION=1.0.0
DEBUG=True
DATABASE_URL=sqlite:///./ngo_management.db
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Use a strong secret key for deployment. Do not commit your actual `.env` file to version control.

**Database Configuration**

The application uses SQLite as its default database.

The database connection is configured through SQLAlchemy, and database models are maintained using a shared declarative base.

**Database Migrations Using Alembic**

Alembic is used to manage database schema changes.

Check the current migration:

```powershell
alembic current
```

View migration history:

```powershell
alembic history
```

View available migration heads:

```powershell
alembic heads
```

Create a new migration after modifying database models:

```powershell
alembic revision --autogenerate -m "describe schema changes"
```

Apply pending migrations:

```powershell
alembic upgrade head
```

Check whether model changes require a migration:

```powershell
alembic check
```

**Running the Application**

Start the FastAPI application using Uvicorn:

```powershell
uvicorn app.main:app --reload
```

The application will run locally at:

```text
http://127.0.0.1:8000
```

**API Documentation**

FastAPI provides interactive API documentation.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

These interfaces allow users and developers to explore and test the available API endpoints.

**Running Tests**

The project uses Pytest for automated testing.

Run the complete test suite:

```powershell
pytest -q
```

Run tests with detailed output:

```powershell
pytest -v
```

**Database Tables**

The system contains the following main database tables:

- users
- approvals
- audit_logs
- beneficiaries
- budgets
- campaigns
- donation_receipts
- donations
- donors
- expenses
- impact_records
- milestones
- notifications
- password_reset_tokens
- projects
- resource_allocations
- resources
- tasks
- volunteer_assignments
- volunteers

**Security Features**

- JWT-based authentication
- Password hashing
- Role-based access control
- Protected API endpoints
- Input validation using Pydantic
- Audit logging
- Token expiry management
- Password reset functionality

**Conclusion**

The NGO Management System provides a centralized backend solution for managing NGO operations. It helps organize beneficiaries, donors, donations, volunteers, projects, financial records, resources, and administrative activities.

The application is built using FastAPI with SQLAlchemy and SQLite, while Alembic manages database migrations. Automated testing with Pytest helps verify the functionality and reliability of the application.

**Project Status**

Backend development and the initial Alembic migration setup have been completed. The project is prepared for final testing and submission.
