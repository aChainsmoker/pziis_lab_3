from dataclasses import dataclass

from src.domain.entities import DataType


@dataclass(frozen=True)
class RecordView:
    """Safe presentation model with confidential content already decrypted."""

    id: int
    title: str
    content: str
    data_type: DataType
