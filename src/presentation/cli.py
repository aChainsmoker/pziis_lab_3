from src.application.dto import RecordView
from src.application.use_cases import DataUseCases
from src.domain.entities import DataType
from src.domain.errors import DomainError


class ConsoleApplication:
    def __init__(self, use_cases: DataUseCases) -> None:
        self._use_cases = use_cases

    def run(self) -> None:
        print("Приложение для работы с данными в оперативной памяти")
        print("Конфиденциальное содержимое хранится в зашифрованном виде.\n")
        while True:
            self._print_menu()
            try:
                command = input("Выберите действие: ").strip()
                if command == "0":
                    print("Работа завершена.")
                    return
                if command == "1":
                    self._create()
                elif command == "2":
                    self._list()
                elif command == "3":
                    self._show()
                elif command == "4":
                    self._update()
                elif command == "5":
                    self._delete()
                else:
                    print("Неизвестная команда. Выберите пункт от 0 до 5.")
            except (DomainError, ValueError) as error:
                print(f"Ошибка: {error}")
            except (EOFError, KeyboardInterrupt):
                print("\nРабота завершена.")
                return
            print()

    @staticmethod
    def _print_menu() -> None:
        print("1. Создать запись")
        print("2. Показать все записи")
        print("3. Показать запись")
        print("4. Обновить запись")
        print("5. Удалить запись")
        print("0. Выход")

    def _create(self) -> None:
        data_type = self._read_type()
        title = input("Название: ")
        content = input("Содержимое: ")
        record = self._use_cases.create(title, content, data_type)
        print(f"Запись создана. ID: {record.id}")

    def _list(self) -> None:
        records = self._use_cases.list()
        if not records:
            print("Записей пока нет.")
            return
        for record in records:
            print(f"ID: {record.id} | {record.data_type.display_name} | {record.title}")

    def _show(self) -> None:
        record = self._use_cases.get(self._read_id())
        self._print_record(record)

    def _update(self) -> None:
        record_id = self._read_id()
        print("Введите новые значения.")
        data_type = self._read_type()
        title = input("Название: ")
        content = input("Содержимое: ")
        record = self._use_cases.update(record_id, title, content, data_type)
        print(f"Запись {record.id} обновлена.")

    def _delete(self) -> None:
        record_id = self._read_id()
        confirmation = input(f"Удалить запись {record_id}? [д/н]: ").strip().lower()
        if confirmation not in {"д", "да", "y", "yes"}:
            print("Удаление отменено.")
            return
        self._use_cases.delete(record_id)
        print("Запись удалена.")

    @staticmethod
    def _read_id() -> int:
        value = input("ID записи: ").strip()
        if not value.isdigit() or int(value) <= 0:
            raise ValueError("ID должен быть положительным целым числом.")
        return int(value)

    @staticmethod
    def _read_type() -> DataType:
        value = input("Тип данных (1 - неконфиденциальные, 2 - конфиденциальные): ").strip()
        if value == "1":
            return DataType.PUBLIC
        if value == "2":
            return DataType.CONFIDENTIAL
        raise ValueError("Выберите тип 1 или 2.")

    @staticmethod
    def _print_record(record: RecordView) -> None:
        print(f"ID: {record.id}")
        print(f"Тип: {record.data_type.display_name}")
        print(f"Название: {record.title}")
        print(f"Содержимое: {record.content}")
