from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ALFA_CORE_OK"}