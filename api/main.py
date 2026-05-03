import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from jose import jwt
from pydantic import BaseModel

app = FastAPI()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

DEMO_USERNAME = os.getenv("API_USERNAME")
DEMO_PASSWORD = os.getenv("API_PASSWORD")


class LoginRequest(BaseModel):
    username: str
    password: str


def create_access_token(username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": username,
        "exp": expires_at,
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


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