import os
import logging
from fastapi import FastAPI
from terminus.database import create_all_tables
from terminus.routers import home, definition, candidate, terms

# Ensure logs/ directory exists
os.makedirs("logs", exist_ok=True)
os.makedirs("/app/data", exist_ok=True)

# Create a formatter
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# File handler
file_handler = logging.FileHandler("logs/terminus.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

logger = logging.getLogger(__name__)

# Create database tables (if not already created)
create_all_tables()

app = FastAPI()

# Include the routers from the dedicated modules
app.include_router(home.router)
app.include_router(definition.router)
app.include_router(candidate.router)
app.include_router(terms.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("terminus.main:app", host="0.0.0.0", port=8000, reload=True)
