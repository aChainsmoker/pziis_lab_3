from src.domain.entities import DataRecord, DataType
from src.domain.errors import RecordNotFoundError


class InMemoryDataRepository:
    """Repository whose only storage is the current process memory."""

    def __init__(self) -> None:
        self._records: dict[int, DataRecord] = {}
        self._next_id = 1

    def create(self, title: str, content: str, data_type: str) -> DataRecord:
        record = DataRecord(self._next_id, title, content, DataType(data_type))
        self._records[record.id] = record
        self._next_id += 1
        return record

    def list(self) -> list[DataRecord]:
        return list(sorted(self._records.values(), key=lambda record: record.id))

    def get(self, record_id: int) -> DataRecord | None:
        return self._records.get(record_id)

    def update(self, record_id: int, title: str, content: str, data_type: str) -> DataRecord:
        if record_id not in self._records:
            raise RecordNotFoundError(f"Запись с ID {record_id} не найдена.")
        record = DataRecord(record_id, title, content, DataType(data_type))
        self._records[record_id] = record
        return record

    def delete(self, record_id: int) -> None:
        if record_id not in self._records:
            raise RecordNotFoundError(f"Запись с ID {record_id} не найдена.")
        del self._records[record_id]
