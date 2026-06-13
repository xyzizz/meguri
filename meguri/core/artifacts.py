from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from meguri.core.models import Artifact


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(self, name: str, text: str, *, kind: str = "text", metadata: dict[str, Any] | None = None) -> Artifact:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return Artifact(name=name, path=str(path), kind=kind, metadata=metadata or {})

    def write_json(self, name: str, data: Any, *, metadata: dict[str, Any] | None = None) -> Artifact:
        return self.write_text(
            name,
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            kind="json",
            metadata=metadata,
        )

