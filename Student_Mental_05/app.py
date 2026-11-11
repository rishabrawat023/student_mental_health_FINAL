import os
import json
import hmac
import secrets
import hashlib
import sqlite3
import string
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, EmailStr
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "database.db"))

app = FastAPI(title="Student Mental Health Score", version="2.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "replace-this-secret-before-deployment"),
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return f"{salt.hex()}${digest.hex()}"

def check_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 310000
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def initialize_database():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            institution TEXT NOT NULL DEFAULT '',
            course TEXT NOT NULL DEFAULT '',
            age INTEGER NOT NULL,
            gender TEXT NOT NULL DEFAULT 'Prefer not to say',
            country TEXT NOT NULL DEFAULT '',
            academic_level TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            score REAL NOT NULL,
            answers_json TEXT NOT NULL,
            components_json TEXT NOT NULL,
            recommendations_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        admin_name = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin@12345")
        if not con.execute("SELECT 1 FROM admins WHERE username=?", (admin_name,)).fetchone():
            con.execute(
                "INSERT INTO admins(username,password_hash,created_at) VALUES(?,?,?)",
                (admin_name, hash_password(admin_password), utc_now()),
            )

@app.on_event("startup")
def startup():
    initialize_database()

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/status")
def status():
    return {"status": "ok", "database": "sqlite"}

class RegisterData(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    institution: str = Field(default="", max_length=150)
    course: str = Field(default="", max_length=120)
    age: int = Field(ge=10, le=100)
    gender: str = Field(default="Prefer not to say", max_length=40)
    country: str = Field(default="", max_length=100)
    academic_level: str = Field(default="", max_length=60)
    password: str = Field(min_length=8, max_length=128)
    answers: dict

class LoginData(BaseModel):
    student_id: str
    password: str

class ProfileData(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    institution: str = Field(default="", max_length=150)
    course: str = Field(default="", max_length=120)
    age: int = Field(ge=10, le=100)
    gender: str = Field(default="Prefer not to say", max_length=40)
    country: str = Field(default="", max_length=100)
    academic_level: str = Field(default="", max_length=60)

class AssessmentData(BaseModel):
    answers: dict

class AdminLoginData(BaseModel):
    username: str
    password: str

def student_session(request: Request):
    sid = request.session.get("student_id")
    if not sid:
        raise HTTPException(401, "Please log in to continue.")
    with connect() as con:
        row = con.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
    if not row:
        request.session.clear()
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return dict(row)

def admin_session(request: Request):
    username = request.session.get("admin")
    if not username:
        raise HTTPException(401, "Administrator login required.")
    return username

def number(answers, key, default, low, high):
    try:
        value = float(answers.get(key, default))
    except (TypeError, ValueError):
        raise HTTPException(422, f"Invalid value for {key}.")
    if not low <= value <= high:
        raise HTTPException(422, f"{key} must be between {low} and {high}.")
    return value

def calculate_wellness(answers):
    # Transparent habit-based reflection estimate; not a clinical screening instrument.
    sleep = number(answers, "sleep_hours_per_night", 7.5, 0, 24)
    activity = number(answers, "physical_activity_hours", 0.5, 0, 24)
    social = number(answers, "avg_daily_usage_hours", 3, 0, 24)
    unlocks = number(answers, "daily_unlocks", 60, 0, 10000)
    study = number(answers, "study_hours", 5, 0, 24)
    stress = str(answers.get("stress_level", "Medium"))
    stress_map = {"Low": 9.0, "Medium": 7.0, "High": 4.5, "Very High": 2.5}
    if stress not in stress_map:
        raise HTTPException(422, "Choose a valid stress level.")

    components = {
        "Sleep": max(0, 10 - abs(sleep - 8) * 1.6),
        "Physical activity": min(10, activity * 8),
        "Stress management": stress_map[stress],
        "Study balance": max(0, 10 - max(0, study - 6) * 1.2 - max(0, 2 - study) * 0.8),
        "Digital balance": max(0, 10 - max(0, social - 2) * 1.15 - max(0, unlocks - 80) / 100),
    }
    score = round(sum(components.values()) / len(components), 1)

    tips = []
    if sleep < 7:
        tips.append("Try moving bedtime earlier in small steps and keep a consistent wake-up time; many students need 7–9 hours.")
    elif sleep > 9:
        tips.append("Keep a regular sleep and wake schedule and notice whether long sleep is paired with daytime tiredness.")
    else:
        tips.append("Protect your sleep routine with a calm wind-down and less screen time just before bed.")
    if activity < 0.5:
        tips.append("Start with a comfortable 15–20 minute walk or gentle movement break on most days.")
    else:
        tips.append("Keep physical activity enjoyable and sustainable; walking, cycling, sports and stretching all count.")
    if stress in ("High", "Very High"):
        tips.append("Try a short breathing exercise, journaling, or breaking one large task into smaller steps. Consider talking with someone you trust.")
    else:
        tips.append("Continue using helpful coping strategies and schedule short recovery breaks between demanding tasks.")
    if study > 8:
        tips.append("Use focused study blocks with planned breaks and protect time for meals, rest and non-academic activities.")
    else:
        tips.append("Keep a realistic daily priority list and balance study time with rest and social connection.")
    if social > 4 or unlocks > 100:
        tips.append("Try a screen-free study period, disable non-essential notifications and choose specific times to check social apps.")
    else:
        tips.append("Maintain intentional digital habits and make room for offline activities and relationships.")
    return score, components, tips

def store_assessment(sid, answers):
    score, components, tips = calculate_wellness(answers)
    with connect() as con:
        con.execute(
            """INSERT INTO assessments(student_id,score,answers_json,components_json,recommendations_json,created_at)
               VALUES(?,?,?,?,?,?)""",
            (sid, score, json.dumps(answers), json.dumps(components), json.dumps(tips), utc_now()),
        )
    return {"score": score, "components": components, "recommendations": tips}

def new_student_id():
    return "STU-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

@app.post("/api/register")
def register(data: RegisterData, request: Request):
    sid = new_student_id()
    try:
        with connect() as con:
            con.execute(
                """INSERT INTO students(student_id,full_name,email,institution,course,age,gender,country,
                   academic_level,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, data.full_name.strip(), str(data.email).lower(), data.institution.strip(),
                 data.course.strip(), data.age, data.gender, data.country.strip(), data.academic_level,
                 hash_password(data.password), utc_now()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This email is already registered. Please log in.")
    request.session.clear()
    request.session["student_id"] = sid
    return {"student_id": sid, **store_assessment(sid, data.answers)}

@app.post("/api/login")
def login(data: LoginData, request: Request):
    with connect() as con:
        row = con.execute("SELECT * FROM students WHERE student_id=?", (data.student_id.strip().upper(),)).fetchone()
    if not row or not check_password(data.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect Student ID or password.")
    request.session.clear()
    request.session["student_id"] = row["student_id"]
    return {"message": "Login successful", "student_id": row["student_id"]}

@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}

@app.get("/api/me")
def get_me(student=Depends(student_session)):
    student.pop("password_hash", None)
    return student

@app.put("/api/me")
def update_me(data: ProfileData, student=Depends(student_session)):
    try:
        with connect() as con:
            con.execute(
                """UPDATE students SET full_name=?,email=?,institution=?,course=?,age=?,gender=?,country=?,
                   academic_level=? WHERE student_id=?""",
                (data.full_name.strip(), str(data.email).lower(), data.institution.strip(), data.course.strip(),
                 data.age, data.gender, data.country.strip(), data.academic_level, student["student_id"]),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That email address is already registered.")
    return {"message": "Profile updated"}

@app.post("/api/assessments")
def create_assessment(data: AssessmentData, student=Depends(student_session)):
    return store_assessment(student["student_id"], data.answers)

@app.get("/api/reports")
def get_reports(student=Depends(student_session)):
    with connect() as con:
        rows = con.execute(
            """SELECT id,score,answers_json,components_json,recommendations_json,created_at
               FROM assessments WHERE student_id=? ORDER BY id DESC LIMIT 100""",
            (student["student_id"],),
        ).fetchall()
    return [{
        "id": r["id"], "score": r["score"], "answers": json.loads(r["answers_json"]),
        "components": json.loads(r["components_json"]),
        "recommendations": json.loads(r["recommendations_json"]), "created_at": r["created_at"]
    } for r in rows]

@app.post("/api/admin/login")
def admin_login(data: AdminLoginData, request: Request):
    with connect() as con:
        row = con.execute("SELECT * FROM admins WHERE username=?", (data.username.strip(),)).fetchone()
    if not row or not check_password(data.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect administrator username or password.")
    request.session.clear()
    request.session["admin"] = row["username"]
    return {"message": "Administrator login successful"}

@app.post("/api/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin", None)
    return {"message": "Logged out"}

@app.get("/api/admin/summary")
def admin_summary(admin=Depends(admin_session)):
    with connect() as con:
        students = con.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
        reports = con.execute("SELECT COUNT(*) n FROM assessments").fetchone()["n"]
        avg = con.execute("SELECT AVG(score) n FROM assessments").fetchone()["n"]
    return {"students": students, "assessments": reports, "average_score": round(avg, 1) if avg is not None else None}

@app.get("/api/admin/students")
def admin_students(q: str = "", admin=Depends(admin_session)):
    search = f"%{q.strip()}%"
    with connect() as con:
        rows = con.execute(
            """SELECT s.student_id,s.full_name,s.email,s.institution,s.course,s.age,s.created_at,
               (SELECT score FROM assessments a WHERE a.student_id=s.student_id ORDER BY a.id DESC LIMIT 1) latest_score
               FROM students s WHERE s.full_name LIKE ? OR s.student_id LIKE ? OR s.email LIKE ?
               ORDER BY s.created_at DESC""", (search, search, search)
        ).fetchall()
    return [dict(r) for r in rows]

@app.delete("/api/admin/students/{sid}")
def delete_student(sid: str, admin=Depends(admin_session)):
    with connect() as con:
        cur = con.execute("DELETE FROM students WHERE student_id=?", (sid,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Student not found.")
    return {"message": "Student and associated reports deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001, reload=True)
