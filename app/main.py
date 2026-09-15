from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, users, locations, assets, asset_sets, condition_logs, dashboard, lookups, sync

app = FastAPI(title="Fixed Asset Manager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(locations.router)
app.include_router(assets.router)
app.include_router(asset_sets.router)
app.include_router(condition_logs.router)
app.include_router(dashboard.router)
app.include_router(lookups.router)
app.include_router(sync.router)


@app.get("/health")
def health():
    return {"status": "ok"}
