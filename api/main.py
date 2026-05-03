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

app = FastAPI()
security = HTTPBearer()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

DEMO_USERNAME = os.getenv("API_USERNAME")
DEMO_PASSWORD = os.getenv("API_PASSWORD")

ANSIBLE_ROOT = Path("/ansible")
ROLES_DIR = ANSIBLE_ROOT / "roles"

class LoginRequest(BaseModel):
    username: str
    password: str

class RunRequest(BaseModel):
    target_name: str
    role_name: str

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

@app.get("/")
def root():
    return {"message": "Ansible Roller API running"}


@app.post("/login")
def login(request: LoginRequest):
    if request.username != DEMO_USERNAME or request.password != DEMO_PASSWORD:
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

    # Targets will be fetched dynamically after Postgres is implemented
    if request.target_name not in ["target1", "target2"]:
        raise HTTPException(status_code=404, detail=f"Target '{request.target_name}' not found")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        inventory_file = temp_path / "hosts"
        playbook_file = temp_path / "playbook.yml"

        inventory_file.write_text(
            f"""[target]
{request.target_name} ansible_host={request.target_name} ansible_user=ansible ansible_password=ansible ansible_python_interpreter=/usr/bin/python3
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