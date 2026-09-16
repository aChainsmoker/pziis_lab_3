from dataclasses import dataclass
from enum import Enum


class DataType(str, Enum):
    PUBLIC = "public"
    CONFIDENTIAL = "confidential"

    @property
    def display_name(self) -> str:
        return {
            DataType.PUBLIC: "неконфиденциальные",
            DataType.CONFIDENTIAL: "конфиденциальные",
        }[self]


@dataclass(frozen=True)
class DataRecord:
    """A record held by the repository.

    For confidential records, ``title`` and ``content`` are ciphertext.
    Decryption belongs to the application layer and is never performed by the
    repository.
    """

    id: int
    title: str
    content: str
    data_type: DataType
