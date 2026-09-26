from fastapi import FastAPI
from app.mcp_server import mcp

app = FastAPI(title="prompt-regression-mcp")

@app.get("/health")
def health():
    return {"status": "ok", "service": "prompt-regression-mcp"}

app.mount("/mcp", mcp.http_app())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
