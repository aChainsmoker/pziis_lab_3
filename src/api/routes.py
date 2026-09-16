from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas import DataInput, DataOutput
from src.application.dto import RecordView
from src.application.use_cases import DataUseCases
from src.domain.entities import DataType
from src.domain.errors import DomainError, RecordNotFoundError, ValidationError


def create_data_router(use_cases: DataUseCases) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["data"])

    @router.get("/public-data", response_model=list[DataOutput])
    def list_public_data(search: str | None = Query(default=None)) -> list[DataOutput]:
        return _filter_and_map(use_cases.list(), DataType.PUBLIC, search)

    @router.post("/public-data", response_model=DataOutput, status_code=status.HTTP_201_CREATED)
    def create_public_data(data: DataInput) -> DataOutput:
        return _map(use_cases.create(data.title, data.content, DataType.PUBLIC))

    @router.get("/public-data/{record_id}", response_model=DataOutput)
    def get_public_data(record_id: int) -> DataOutput:
        return _get(use_cases, record_id, DataType.PUBLIC)

    @router.put("/public-data/{record_id}", response_model=DataOutput)
    def update_public_data(record_id: int, data: DataInput) -> DataOutput:
        return _update(use_cases, record_id, data, DataType.PUBLIC)

    @router.delete("/public-data/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_public_data(record_id: int) -> None:
        _delete(use_cases, record_id, DataType.PUBLIC)

    @router.get("/confidential", response_model=list[DataOutput])
    def list_confidential_data(search: str | None = Query(default=None)) -> list[DataOutput]:
        return _filter_and_map(use_cases.list(), DataType.CONFIDENTIAL, search)

    @router.post("/confidential", response_model=DataOutput, status_code=status.HTTP_201_CREATED)
    def create_confidential_data(data: DataInput) -> DataOutput:
        return _map(use_cases.create(data.title, data.content, DataType.CONFIDENTIAL))

    @router.get("/confidential/{record_id}", response_model=DataOutput)
    def get_confidential_data(record_id: int) -> DataOutput:
        return _get(use_cases, record_id, DataType.CONFIDENTIAL)

    @router.put("/confidential/{record_id}", response_model=DataOutput)
    def update_confidential_data(record_id: int, data: DataInput) -> DataOutput:
        return _update(use_cases, record_id, data, DataType.CONFIDENTIAL)

    @router.delete("/confidential/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_confidential_data(record_id: int) -> None:
        _delete(use_cases, record_id, DataType.CONFIDENTIAL)

    return router


def _filter_and_map(records: list[RecordView], data_type: DataType, search: str | None) -> list[DataOutput]:
    records = [record for record in records if record.data_type is data_type]
    if search:
        needle = search.casefold()
        records = [record for record in records if needle in record.title.casefold() or needle in record.content.casefold()]
    return [_map(record) for record in records]


def _get(use_cases: DataUseCases, record_id: int, data_type: DataType) -> DataOutput:
    return _map(_load_checked(use_cases, record_id, data_type))


def _update(use_cases: DataUseCases, record_id: int, data: DataInput, data_type: DataType) -> DataOutput:
    _load_checked(use_cases, record_id, data_type)
    try:
        return _map(use_cases.update(record_id, data.title, data.content, data_type))
    except DomainError as error:
        raise _http_error(error) from error


def _delete(use_cases: DataUseCases, record_id: int, data_type: DataType) -> None:
    _load_checked(use_cases, record_id, data_type)
    try:
        use_cases.delete(record_id)
    except DomainError as error:
        raise _http_error(error) from error


def _load_checked(use_cases: DataUseCases, record_id: int, data_type: DataType) -> RecordView:
    try:
        record = use_cases.get(record_id)
    except DomainError as error:
        raise _http_error(error) from error
    if record.data_type is not data_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена.")
    return record


def _map(record: RecordView) -> DataOutput:
    return DataOutput(id=record.id, title=record.title, content=record.content)


def _http_error(error: DomainError) -> HTTPException:
    if isinstance(error, RecordNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
