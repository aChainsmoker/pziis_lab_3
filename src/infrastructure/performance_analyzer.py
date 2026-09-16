from __future__ import annotations

import csv
import os
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import psutil


@dataclass(frozen=True)
class PerformanceSample:
    run_id: int
    measured_at_utc: str
    stage: str
    data_type: str
    records_count: int
    elapsed_ms: float
    cpu_time_ms: float
    cpu_percent: float
    rss_before_mb: float
    rss_after_mb: float
    rss_delta_mb: float
    tracemalloc_current_mb: float
    tracemalloc_peak_mb: float


class PerformanceAnalyzer:
    """Measures process memory and CPU usage around an application operation."""

    def __init__(self, run_id: int, process: psutil.Process | None = None) -> None:
        self.run_id = run_id
        self.process = process or psutil.Process(os.getpid())
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    @contextmanager
    def measure(self, stage: str, data_type: str, records_count: int) -> Iterator[None]:
        tracemalloc.reset_peak()
        rss_before = self.process.memory_info().rss
        cpu_before = self._cpu_time_seconds()
        started = time.perf_counter()

        try:
            yield
        finally:
            elapsed_seconds = time.perf_counter() - started
            cpu_seconds = max(0.0, self._cpu_time_seconds() - cpu_before)
            rss_after = self.process.memory_info().rss
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            elapsed_ms = elapsed_seconds * 1000
            cpu_time_ms = cpu_seconds * 1000
            self.samples.append(
                PerformanceSample(
                    run_id=self.run_id,
                    measured_at_utc=datetime.now(timezone.utc).isoformat(),
                    stage=stage,
                    data_type=data_type,
                    records_count=records_count,
                    elapsed_ms=round(elapsed_ms, 3),
                    cpu_time_ms=round(cpu_time_ms, 3),
                    cpu_percent=round((cpu_seconds / elapsed_seconds) * 100, 3)
                    if elapsed_seconds > 0
                    else 0.0,
                    rss_before_mb=round(rss_before / 1024 / 1024, 3),
                    rss_after_mb=round(rss_after / 1024 / 1024, 3),
                    rss_delta_mb=round((rss_after - rss_before) / 1024 / 1024, 3),
                    tracemalloc_current_mb=round(current_bytes / 1024 / 1024, 3),
                    tracemalloc_peak_mb=round(peak_bytes / 1024 / 1024, 3),
                )
            )

    @property
    def samples(self) -> list[PerformanceSample]:
        if not hasattr(self, "_samples"):
            self._samples: list[PerformanceSample] = []
        return self._samples

    def _cpu_time_seconds(self) -> float:
        cpu_times = self.process.cpu_times()
        return cpu_times.user + cpu_times.system


class PerformanceLogWriter:
    """Persists analyzer samples as CSV and a readable Markdown table."""

    field_names = list(PerformanceSample.__dataclass_fields__.keys())

    def write_csv(self, samples: list[PerformanceSample], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=self.field_names)
            writer.writeheader()
            writer.writerows(asdict(sample) for sample in samples)

    def write_markdown(self, samples: list[PerformanceSample], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Результаты анализа памяти и процессорного времени",
            "",
            "Измерения выполнены для in-memory приложения. `RSS` показывает память процесса, "
            "а `tracemalloc` — Python-аллокации.",
            "",
            "## Средние значения по этапам",
            "",
            "| Этап | Тип данных | Записей | Время, мс | CPU time, мс | CPU, % | RSS до, МБ | RSS после, МБ | RSS delta, МБ | Peak Python, МБ |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        groups: dict[tuple[str, str, int], list[PerformanceSample]] = {}
        for sample in samples:
            groups.setdefault((sample.stage, sample.data_type, sample.records_count), []).append(sample)
        for key, group in groups.items():
            stage, data_type, records_count = key
            lines.append(
                "| {stage} | {data_type} | {count} | {elapsed:.3f} | {cpu_time:.3f} | {cpu:.3f} | "
                "{rss_before:.3f} | {rss_after:.3f} | {rss_delta:.3f} | {peak:.3f} |".format(
                    stage=stage,
                    data_type=data_type,
                    count=records_count,
                    elapsed=_average(group, "elapsed_ms"),
                    cpu_time=_average(group, "cpu_time_ms"),
                    cpu=_average(group, "cpu_percent"),
                    rss_before=_average(group, "rss_before_mb"),
                    rss_after=_average(group, "rss_after_mb"),
                    rss_delta=_average(group, "rss_delta_mb"),
                    peak=_average(group, "tracemalloc_peak_mb"),
                )
            )
        lines.extend(["", "## Отдельные измерения", ""])
        lines.append("| Запуск | Этап | Тип данных | Записей | Время, мс | CPU time, мс | RSS delta, МБ | Peak Python, МБ |")
        lines.append("|---:|---|---|---:|---:|---:|---:|---:|")
        for sample in samples:
            lines.append(
                f"| {sample.run_id} | {sample.stage} | {sample.data_type} | {sample.records_count} | "
                f"{sample.elapsed_ms:.3f} | {sample.cpu_time_ms:.3f} | {sample.rss_delta_mb:.3f} | "
                f"{sample.tracemalloc_peak_mb:.3f} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _average(samples: list[PerformanceSample], field_name: str) -> float:
    return round(sum(float(getattr(sample, field_name)) for sample in samples) / len(samples), 3)
