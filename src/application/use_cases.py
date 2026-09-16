from src.application.dto import RecordView
from src.domain.entities import DataRecord, DataType
from src.domain.errors import RecordNotFoundError, ValidationError
from src.domain.ports import DataRepository, Encryptor


class DataUseCases:
    def __init__(self, repository: DataRepository, encryptor: Encryptor) -> None:
        self._repository = repository
        self._encryptor = encryptor

    def create(self, title: str, content: str, data_type: DataType) -> RecordView:
        title, content = self._validate(title, content)
        stored_title, stored_content = self._protect(title, content, data_type)
        return self._to_view(self._repository.create(stored_title, stored_content, data_type.value))

    def list(self) -> list[RecordView]:
        return [self._to_view(record) for record in self._repository.list()]

    def get(self, record_id: int) -> RecordView:
        return self._to_view(self._get_record(record_id))

    def update(self, record_id: int, title: str, content: str, data_type: DataType) -> RecordView:
        title, content = self._validate(title, content)
        self._get_record(record_id)
        stored_title, stored_content = self._protect(title, content, data_type)
        return self._to_view(self._repository.update(record_id, stored_title, stored_content, data_type.value))

    def delete(self, record_id: int) -> None:
        self._get_record(record_id)
        self._repository.delete(record_id)

    @staticmethod
    def _validate(title: str, content: str) -> tuple[str, str]:
        title, content = title.strip(), content.strip()
        if not title:
            raise ValidationError("Название не должно быть пустым.")
        if not content:
            raise ValidationError("Содержимое не должно быть пустым.")
        return title, content

    def _get_record(self, record_id: int) -> DataRecord:
        record = self._repository.get(record_id)
        if record is None:
            raise RecordNotFoundError(f"Запись с ID {record_id} не найдена.")
        return record

    def _protect(self, title: str, content: str, data_type: DataType) -> tuple[str, str]:
        if data_type is DataType.CONFIDENTIAL:
            return self._encryptor.encrypt(title), self._encryptor.encrypt(content)
        return title, content

    def _to_view(self, record: DataRecord) -> RecordView:
        title, content = (
            self._encryptor.decrypt(record.title),
            self._encryptor.decrypt(record.content),
        ) if record.data_type is DataType.CONFIDENTIAL else (
            record.title,
            record.content,
        )
        return RecordView(record.id, title, content, record.data_type)
