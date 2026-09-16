from cryptography.fernet import Fernet


class FernetEncryptor:
    def __init__(self, key: bytes) -> None:
        self._cipher = Fernet(key)

    @classmethod
    def generate(cls) -> "FernetEncryptor":
        return cls(Fernet.generate_key())

    def encrypt(self, value: str) -> str:
        return self._cipher.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._cipher.decrypt(value.encode("utf-8")).decode("utf-8")
