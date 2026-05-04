#import os
#from datetime import datetime, timedelta, timezone

#from fastapi import FastAPI, HTTPException
#from jose import jwt
#from pydantic import BaseModel

import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

import psycopg2
from cryptography.fernet import Fernet

app = FastAPI()
security = HTTPBearer()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")

ANSIBLE_ROOT = Path("/ansible")
ROLES_DIR = ANSIBLE_ROOT / "roles"

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
fernet = Fernet(ENCRYPTION_KEY.encode())


def encrypt_secret(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return fernet.decrypt(value.encode()).decode()


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def create_access_token(username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": username,
        "exp": expires_at,
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return username

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_target_by_name(target_name: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, host, username, password
                FROM targets
                WHERE name = %s;
                """,
                (target_name,),
            )
            return cur.fetchone()


class LoginRequest(BaseModel):
    username: str
    password: str

class RunRequest(BaseModel):
    target_name: str
    role_name: str

class TargetRequest(BaseModel):
    name: str
    host: str
    username: str
    password: str


@app.on_event("startup")
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS targets (
                    name TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL
                );
                """
            )
            conn.commit()


@app.get("/")
def root():
    return {"message": "Ansible Roller API running"}


@app.post("/login")
def login(request: LoginRequest):
    if request.username != API_USERNAME or request.password != API_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(request.username)

    return {
        "access_token": token,
        "token_type": "bearer",
    }

@app.post("/run")
def run_ansible(request: RunRequest, username: str = Depends(verify_token)):
    role_path = ROLES_DIR / request.role_name

    if not role_path.exists():
        raise HTTPException(status_code=404, detail=f"Role '{request.role_name}' not found")

    target = get_target_by_name(request.target_name)

    if target is None:
        raise HTTPException(status_code=404, detail=f"Target '{request.target_name}' not found")

    target_name, target_host, target_username, encrypted_password = target
    target_password = decrypt_secret(encrypted_password)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        inventory_file = temp_path / "hosts"
        playbook_file = temp_path / "playbook.yml"

        inventory_file.write_text(
            f"""[target]
    {target_name} ansible_host={target_host} ansible_user={target_username} ansible_password={target_password}
"""
            )

        playbook_file.write_text(
            f"""---
- name: Apply requested role
  hosts: target
  become: true
  roles:
    - {request.role_name}
"""
        )

        command = [
            "ansible-playbook",
            "-i",
            str(inventory_file),
            str(playbook_file),
        ]

        result = subprocess.run(
            command,
            cwd=str(ANSIBLE_ROOT),
            capture_output=True,
            text=True,
        )

    return {
        "requested_by": username,
        "target_name": request.target_name,
        "role_name": request.role_name,
        "status": "successful" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@app.put("/targets")
def upsert_target(request: TargetRequest, username: str = Depends(verify_token)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            encrypted_password = encrypt_secret(request.password)
            cur.execute(
                """
                INSERT INTO targets (name, host, username, password)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name)
                DO UPDATE SET
                    host = EXCLUDED.host,
                    username = EXCLUDED.username,
                    password = EXCLUDED.password;
                """,
                (
                    request.name,
                    request.host,
                    request.username,
                    encrypted_password,
                ),
            )
            conn.commit()

    return {"message": f"Target '{request.name}' saved"}


@app.get("/targets")
def list_targets(username: str = Depends(verify_token)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, host, username
                FROM targets
                ORDER BY name;
                """
            )
            rows = cur.fetchall()

    return {
        "targets": [
            {
                "name": row[0],
                "host": row[1],
                "username": row[2],
            }
            for row in rows
        ]
    }


@app.delete("/targets/{target_name}")
def delete_target(target_name: str, username: str = Depends(verify_token)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM targets WHERE name = %s;",
                (target_name,),
            )
            deleted = cur.rowcount
            conn.commit()

    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Target '{target_name}' not found")

    return {"message": f"Target '{target_name}' deleted"}