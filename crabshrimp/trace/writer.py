from pathlib import Path
from crabshrimp.models.trace import TraceStep


class TraceWriter:
    def __init__(self, output_path: str):
        self._path = Path(output_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a", encoding="utf-8")

    def write(self, step: TraceStep) -> None:
        self._file.write(step.model_dump_json() + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NullTraceWriter:
    """No-op writer used when trace persistence is disabled."""

    def write(self, step: TraceStep) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
