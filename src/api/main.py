"""
FastAPI приложение для REST API
(Будет реализовано на этапе 6)
"""
from fastapi import FastAPI

app = FastAPI(
    title="Courier Route Optimization API",
    description="REST API для управления заказами и маршрутами",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {"message": "Courier Route Optimization API", "status": "ok"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

