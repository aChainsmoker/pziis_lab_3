from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.application.use_cases import DataUseCases
from src.domain.entities import DataType
from src.infrastructure.fernet_encryptor import FernetEncryptor
from src.infrastructure.in_memory_repository import InMemoryDataRepository
from src.infrastructure.performance_analyzer import PerformanceAnalyzer, PerformanceLogWriter, PerformanceSample


RECORDS_PER_TYPE = 100000


def run_benchmark(runs: int) -> list[PerformanceSample]:
    all_samples: list[PerformanceSample] = []
    for run_id in range(1, runs + 1):
        repository = InMemoryDataRepository()
        use_cases = DataUseCases(repository, FernetEncryptor.generate())
        analyzer = PerformanceAnalyzer(run_id)

        with analyzer.measure("baseline", "none", 0):
            pass
        with analyzer.measure("create", "public", RECORDS_PER_TYPE):
            for index in range(RECORDS_PER_TYPE):
                use_cases.create(f"Public title {index}", f"Public content {index}", DataType.PUBLIC)
        with analyzer.measure("create", "confidential", RECORDS_PER_TYPE):
            for index in range(RECORDS_PER_TYPE):
                use_cases.create(f"Secret title {index}", f"Secret content {index}", DataType.CONFIDENTIAL)
        with analyzer.measure("list_and_decrypt", "both", RECORDS_PER_TYPE * 2):
            records = use_cases.list()
            if len(records) != RECORDS_PER_TYPE * 2:
                raise RuntimeError(f"Expected 200 records, got {len(records)}")
        with analyzer.measure("update", "both", RECORDS_PER_TYPE * 2):
            for record in records:
                use_cases.update(record.id, f"Updated {record.title}", f"Updated {record.content}", record.data_type)
        with analyzer.measure("delete", "both", RECORDS_PER_TYPE * 2):
            for record in records:
                use_cases.delete(record.id)
        all_samples.extend(analyzer.samples)
    return all_samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark memory and CPU usage of the lab application.")
    parser.add_argument("--runs", type=int, default=5, help="Number of independent runs (default: 5).")
    args = parser.parse_args()
    if args.runs <= 0:
        raise SystemExit("--runs must be a positive integer")

    samples = run_benchmark(args.runs)
    output_dir = PROJECT_ROOT / "analysis"
    writer = PerformanceLogWriter()
    csv_path = output_dir / "performance_results.csv"
    markdown_path = output_dir / "performance_results.md"
    writer.write_csv(samples, csv_path)
    writer.write_markdown(samples, markdown_path)
    print(f"Saved {len(samples)} measurements to:")
    print(csv_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
