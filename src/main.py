from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import create_data_router
from src.application.use_cases import DataUseCases
from src.infrastructure.fernet_encryptor import FernetEncryptor
from src.infrastructure.in_memory_repository import InMemoryDataRepository


def build_application() -> FastAPI:
    repository = InMemoryDataRepository()
    encryptor = FernetEncryptor.generate()
    use_cases = DataUseCases(repository, encryptor)
    application = FastAPI(title="Lab 3 Secure Data")
    application.include_router(create_data_router(use_cases))
    frontend = Path(__file__).resolve().parent.parent / "frontend"
    application.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return application


app = build_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=False)
