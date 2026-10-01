from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging
import sys

# Recognize flags
debug = "debug" in sys.argv

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

if not load_dotenv() and debug:
    logger.error("Failed to load environment.")
    quit(1)

import config  # noqa: E402  (reads the environment loaded above)
from datastore import close_storage, init_storage  # noqa: E402
from routers import (  # noqa: E402
    auth, chats, company, corporate, friends, languages, market, me, missions, puzzles, tickets, users,
)
from schema import bootstrap_admin, create_schema  # noqa: E402

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")

    logger.info("Initializing storage")
    storage = await init_storage()
    await create_schema(storage)
    await bootstrap_admin(storage)

    yield

    logger.info("Closing storage")
    _ = await close_storage()

    logger.info("Shutting down")

app = FastAPI(title="Hack4Seniors API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials="*" not in config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared
app.include_router(auth.router)
app.include_router(languages.router)
app.include_router(market.router)
app.include_router(tickets.router)

# User frontend
app.include_router(me.router)
app.include_router(users.router)
app.include_router(friends.router)
app.include_router(chats.router)
app.include_router(missions.router)
app.include_router(puzzles.router)

# Company frontend
app.include_router(company.router)

# Corporate frontend
app.include_router(corporate.router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
