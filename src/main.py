from fastapi import FastAPI

app = FastAPI(title="Fachsprachen MVP - Dokumentübersetzung")

@app.get("/health")
def health():
    return {"status": "ok"}
