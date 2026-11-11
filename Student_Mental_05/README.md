# Student Mental Health Score — MindSignal (Upgraded)

A universal student wellness web application using **FastAPI, SQLite, HTML, CSS and JavaScript**.

## Features

- Student registration with a generated unique Student ID
- Student login using Student ID and password
- Passwords stored as salted PBKDF2-HMAC-SHA256 hashes
- SQLite database created automatically on first start
- Student profile editing
- Wellness score out of 10 based on sleep, physical activity, stress, study and digital habits
- Personalized, practical recommendations
- Previous assessments, report table and progress chart
- Admin login, student search, aggregate statistics and student-record deletion
- Responsive MindSignal interface adapted from the supplied project design

## Requirements

- Python 3.10+
- VS Code recommended

## Windows setup (PowerShell)

1. Extract the ZIP and open the extracted `Student_Mental_Health_Score` folder in VS Code.
2. Open **Terminal → New Terminal**.
3. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

4. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   and activate again.

5. Install all dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the application:

   ```powershell
   uvicorn app:app --reload
   ```

7. Open **http://127.0.0.1:8000** in Chrome.

The `database.db` SQLite file is created automatically. Do not create tables manually.

## macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000.

## Default administrator

On first database initialization, the app creates:

- Username: `admin`
- Password: `Admin@12345`

Change these credentials before using real student records. Configure them before the first launch using environment variables.

PowerShell:
```powershell
$env:ADMIN_USERNAME="your-admin-name"
$env:ADMIN_PASSWORD="a-long-unique-password"
$env:SESSION_SECRET="replace-with-a-long-random-secret"
uvicorn app:app --reload
```

macOS/Linux:
```bash
export ADMIN_USERNAME="your-admin-name"
export ADMIN_PASSWORD="a-long-unique-password"
export SESSION_SECRET="replace-with-a-long-random-secret"
uvicorn app:app --reload
```

The initial admin is created only if the configured username does not already exist. Changing environment variables later does not overwrite an existing admin account.

For HTTPS deployment, set `COOKIE_SECURE=true` and use a strong random session secret. Do not expose the development server directly to the public internet.

## Project structure

```text
Student_Mental_Health_Score/
├── app.py
├── requirements.txt
├── README.md
├── database.db       # created automatically after first run
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## API routes

- `POST /api/register`
- `POST /api/login`, `POST /api/logout`
- `GET /api/me`, `PUT /api/me`
- `POST /api/assessments`, `GET /api/reports`
- `POST /api/admin/login`, `POST /api/admin/logout`
- `GET /api/admin/summary`, `GET /api/admin/students`
- `DELETE /api/admin/students/{student_id}`
- `GET /api/status`

FastAPI interactive API documentation: http://127.0.0.1:8000/docs

## Important wellbeing note

The wellness score is a transparent, rule-based reflection estimate, not a clinically validated screening instrument or diagnosis. It must not be used to diagnose, rank, or make high-stakes decisions about students. Anyone distressed or concerned about their wellbeing should consider speaking with a qualified professional or trusted support person.

## Existing project database

This upgrade creates a new SQLite database named `database.db` in this project folder. The original uploaded project did not store student accounts or assessment history, so there is no old student database to migrate.
