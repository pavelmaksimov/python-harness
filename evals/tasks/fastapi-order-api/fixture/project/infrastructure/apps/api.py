from fastapi import FastAPI

from project.components.orders.endpoints import router as orders_router

app = FastAPI(title="orders-api")
app.include_router(orders_router)
