# Ansible Roller
Small API service that runs Ansible roles on target hosts.

## Stack
- FastAPI (API)
- PostgreSQL (DB)
- Docker Compose (environment)
- Ansible (automation)

## Architecture
```text
API > PostgreSQL > Ansible > Targets (via SSH)
```

Targets are created by Docker Compose. `/targets` stores connection info, not infrastructure.

---

## Setup
Clone repo:

```bash
git clone <repo>
cd ansible-roller
```

Generate encryption key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create `.env`:
```bash
cp .env.example .env
```

Fill values (see example in .env.example), then run:
```bash
docker compose up --build
```

API docs:
```text
http://localhost:8000/docs
```

---

## Auth
```http
POST /login
```

```json
{
  "username": "admin",
  "password": "admin"
}
```

Use token:
```text
Authorization: Bearer <token>
```

---

## Targets
Register target:
```http
PUT /targets
```

```json
{
  "name": "target1",
  "host": "target1",
  "username": "ansible",
  "password": "ansible"
}
```

List:
```http
GET /targets
```

Delete:
```http
DELETE /targets/{name}
```

---

## Run Ansible
```http
POST /run
```

```json
{
  "target_name": "target1",
  "role_name": "nginx"
}
```

Flow:
- target loaded from DB
- password decrypted
- temporary inventory/playbook created
- `ansible-playbook` executed
- output returned

---