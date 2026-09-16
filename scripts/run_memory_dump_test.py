from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.application.use_cases import DataUseCases
from src.domain.entities import DataType
from src.infrastructure.fernet_encryptor import FernetEncryptor
from src.infrastructure.in_memory_repository import InMemoryDataRepository


CREATE_PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
GENERIC_WRITE = 0x40000000
CREATE_ALWAYS = 2
FILE_ATTRIBUTE_NORMAL = 0x80
MINIDUMP_WITH_FULL_MEMORY = 0x00000002
MINIDUMP_WITH_HANDLE_DATA = 0x00000004
MINIDUMP_WITH_UNLOADED_MODULES = 0x00000020
MINIDUMP_WITH_FULL_MEMORY_INFO = 0x00000800
MINIDUMP_WITH_THREAD_INFO = 0x00001000


class Worker:
    def __init__(self) -> None:
        self.use_cases = DataUseCases(InMemoryDataRepository(), FernetEncryptor.generate())
        self.record_ids: dict[str, int] = {}
        # Keep API-like responses alive until the next phase. This models
        # objects that exist while HTTP responses are being built.
        self.last_responses: dict[str, object] = {}

    def handle(self, payload: dict[str, str]) -> str:
        command = payload.get("command")
        if command == "create":
            data_type = DataType(payload["data_type"])
            response = self.use_cases.create(
                payload["title"],
                payload["content"],
                data_type,
            )
            self.record_ids[data_type.value] = response.id
            self.last_responses[data_type.value] = response
            return "created"
        if command == "update":
            data_type = DataType(payload["data_type"])
            record_id = self.record_ids.get(data_type.value)
            if record_id is None:
                raise RuntimeError("create must be executed first")
            self.last_responses[data_type.value] = self.use_cases.update(
                record_id,
                payload["title"],
                payload["content"],
                data_type,
            )
            return "updated"
        if command == "delete":
            data_type = DataType(payload["data_type"])
            record_id = self.record_ids.get(data_type.value)
            if record_id is None:
                raise RuntimeError("create must be executed first")
            self.use_cases.delete(record_id)
            self.record_ids.pop(data_type.value, None)
            self.last_responses.pop(data_type.value, None)
            return "deleted"
        if command == "exit":
            return "exit"
        raise ValueError(f"Unknown command: {command}")


def worker_main() -> None:
    worker = Worker()
    print("READY", flush=True)
    for raw_command in sys.stdin:
        command = json.loads(raw_command)
        try:
            result = worker.handle(command)
            print(result, flush=True)
            if result == "exit":
                return
        except Exception as error:  # pragma: no cover - diagnostic process path
            print(f"ERROR: {error}", flush=True)


def create_full_dump(pid: int, output_path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Memory dump creation in this script requires Windows.")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    handle_type = ctypes.c_void_p

    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = handle_type
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        handle_type,
        ctypes.c_uint32,
        ctypes.c_uint32,
        handle_type,
    ]
    kernel32.CreateFileW.restype = handle_type
    kernel32.CloseHandle.argtypes = [handle_type]
    kernel32.CloseHandle.restype = ctypes.c_int

    dbghelp.MiniDumpWriteDump.argtypes = [
        handle_type,
        ctypes.c_uint32,
        handle_type,
        ctypes.c_uint32,
        handle_type,
        handle_type,
        handle_type,
    ]
    dbghelp.MiniDumpWriteDump.restype = ctypes.c_int

    process_handle = kernel32.OpenProcess(
        CREATE_PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
        False,
        pid,
    )
    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump_handle = kernel32.CreateFileW(
        str(output_path),
        GENERIC_WRITE,
        0,
        None,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if dump_handle == ctypes.c_void_p(-1).value:
        kernel32.CloseHandle(process_handle)
        raise ctypes.WinError(ctypes.get_last_error())

    dump_type = (
        MINIDUMP_WITH_FULL_MEMORY
        | MINIDUMP_WITH_HANDLE_DATA
        | MINIDUMP_WITH_UNLOADED_MODULES
        | MINIDUMP_WITH_FULL_MEMORY_INFO
        | MINIDUMP_WITH_THREAD_INFO
    )
    try:
        success = dbghelp.MiniDumpWriteDump(process_handle, pid, dump_handle, dump_type, None, None, None)
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(dump_handle)
        kernel32.CloseHandle(process_handle)


def send_command(process: subprocess.Popen[str], payload: dict[str, str], expected: str) -> None:
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("Worker pipes are unavailable")
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    response = process.stdout.readline().strip()
    if response != expected:
        raise RuntimeError(f"Worker returned unexpected response: {response}")


def scan_dumps(output_dir: Path, markers: dict[str, str]) -> Path:
    report_path = output_dir.parent / "memory_strings_analysis.md"
    lines = [
        "# Анализ строк в дампах памяти",
        "",
        "Проверка выполнена автоматически после создания дампов. `Найдена` означает, "
        "что последовательность байтов контрольной строки обнаружена в полном дампе.",
        "",
        "## Результаты",
        "",
        "| Дамп | Тип данных | Этап | Контрольная строка | Результат | Смещение | Кодировка | Извлечённое значение |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    dump_names = (
        ("dump_after_create.dmp", "после создания"),
        ("dump_after_update.dmp", "после обновления"),
        ("dump_after_delete.dmp", "после удаления"),
    )
    for dump_name, stage in dump_names:
        dump_path = output_dir / dump_name
        dump_bytes = dump_path.read_bytes()
        for marker_name, marker_value in markers.items():
            data_type, phase = marker_name.split(":", 1)
            offset, encoding = _find_string(dump_bytes, marker_value)
            result = "Найдена" if offset >= 0 else "Не найдена"
            offset_value = f"0x{offset:X}" if offset >= 0 else "—"
            extracted_value = f"`{marker_value}`" if offset >= 0 else "—"
            lines.append(
                f"| {dump_name} | {data_type} | {stage} | `{phase}` | {result} | "
                f"{offset_value} | {encoding or '—'} | {extracted_value} |"
            )

    lines.extend(
        [
            "",
            "## Интерпретация",
            "",
            "- Неконфиденциальные данные хранятся в репозитории открытым текстом, поэтому их строки могут находиться в дампе непосредственно из словаря репозитория.",
            "- Конфиденциальные данные в репозитории хранятся в зашифрованном виде, но расшифрованные значения временно присутствуют в объектах ответа приложения.",
            "- После обновления старые значения могут сохраняться из-за временных копий строк и особенностей управления памятью Python.",
            "- После удаления отсутствие записи из словаря не гарантирует мгновенного физического затирания всех копий строки в памяти.",
            "- Автоматический поиск строк не заменяет WinDbg: он показывает наличие контрольных значений, но не описывает владельца каждой копии в heap.",
            "- В отчёт добавляются только контрольные строки теста; полный экспорт всех строк дампа намеренно не выполняется, поскольку он может раскрыть служебные данные и ключи.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _find_string(dump_bytes: bytes, value: str) -> tuple[int, str | None]:
    ascii_offset = dump_bytes.find(value.encode("utf-8"))
    if ascii_offset >= 0:
        return ascii_offset, "ASCII/UTF-8"
    utf16_offset = dump_bytes.find(value.encode("utf-16-le"))
    if utf16_offset >= 0:
        return utf16_offset, "UTF-16LE"
    return -1, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Create three memory dumps around CRUD operations.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "analysis" / "dumps")
    args = parser.parse_args()

    command = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    worker = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        if worker.stdout is None or worker.stdout.readline().strip() != "READY":
            raise RuntimeError("Worker did not start correctly")
        print(f"Worker PID: {worker.pid}")
        public_title = "_".join(("PUBLIC", "TITLE", "12345"))
        public_content = "_".join(("PUBLIC", "CONTENT", "12345"))
        updated_public_title = "_".join(("UPDATED", "PUBLIC", "TITLE", "67890"))
        updated_public_content = "_".join(("UPDATED", "PUBLIC", "CONTENT", "67890"))
        secret_title = "_".join(("SECRET", "TITLE", "12345"))
        secret_content = "_".join(("SECRET", "CONTENT", "12345"))
        updated_secret_title = "_".join(("UPDATED", "TITLE", "67890"))
        updated_secret_content = "_".join(("UPDATED", "CONTENT", "67890"))
        markers = {
            "public:" + public_title: public_title,
            "public:" + public_content: public_content,
            "public:" + updated_public_title: updated_public_title,
            "public:" + updated_public_content: updated_public_content,
            "confidential:" + secret_title: secret_title,
            "confidential:" + secret_content: secret_content,
            "confidential:" + updated_secret_title: updated_secret_title,
            "confidential:" + updated_secret_content: updated_secret_content,
        }
        phases = (
            ({"command": "create", "data_type": "public", "title": public_title, "content": public_content}, "created", None),
            ({"command": "create", "data_type": "confidential", "title": secret_title, "content": secret_content}, "created", "dump_after_create.dmp"),
            ({"command": "update", "data_type": "public", "title": updated_public_title, "content": updated_public_content}, "updated", None),
            ({"command": "update", "data_type": "confidential", "title": updated_secret_title, "content": updated_secret_content}, "updated", "dump_after_update.dmp"),
            ({"command": "delete", "data_type": "public"}, "deleted", None),
            ({"command": "delete", "data_type": "confidential"}, "deleted", "dump_after_delete.dmp"),
        )
        for payload, expected, dump_name in phases:
            send_command(worker, payload, expected)
            if dump_name is not None:
                dump_path = args.output_dir / dump_name
                create_full_dump(worker.pid, dump_path)
                print(f"Created {dump_path}")
        if worker.stdin is not None:
            worker.stdin.write(json.dumps({"command": "exit"}) + "\n")
            worker.stdin.flush()
        worker.wait(timeout=10)
        report_path = scan_dumps(args.output_dir, markers)
        print(f"Saved marker analysis to {report_path}")
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker_main()
    else:
        main()
