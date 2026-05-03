from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Ansible Roller API running"}