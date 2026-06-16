from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from creator_agent.config import Settings


CacheTarget = Literal["samples", "transcripts", "translations", "all"]


class CacheService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def info(self) -> dict[str, Any]:
        return {
            "policy": {
                "usage": "manual_research",
                "low_frequency": True,
                "retains_full_video": False,
                "sample_scope": "first_five_minutes",
            },
            "paths": {
                "samples": self._path_info(Path(self.settings.sample_cache_dir)),
                "transcripts": self._path_info(Path(self.settings.transcript_cache_dir)),
                "translations": self._path_info(Path(self.settings.translation_cache_dir)),
            },
        }

    def clear(self, target: CacheTarget) -> dict[str, Any]:
        targets = ["samples", "transcripts", "translations"] if target == "all" else [target]
        before = self.info()["paths"]
        for name in targets:
            path = self._path_for(name)
            self._clear_path(path)
        after = self.info()["paths"]
        removed_files = sum(before[name]["file_count"] - after[name]["file_count"] for name in targets)
        return {"cleared": {"target": target, "removed_files": max(0, removed_files)}, "paths": after}

    def _path_for(self, name: str) -> Path:
        mapping = {
            "samples": self.settings.sample_cache_dir,
            "transcripts": self.settings.transcript_cache_dir,
            "translations": self.settings.translation_cache_dir,
        }
        if name not in mapping:
            raise ValueError("Unknown cache target.")
        return Path(mapping[name])

    def _path_info(self, path: Path) -> dict[str, Any]:
        path.mkdir(parents=True, exist_ok=True)
        files = [item for item in path.rglob("*") if item.is_file()]
        size_bytes = sum(item.stat().st_size for item in files)
        return {"path": str(path), "file_count": len(files), "size_bytes": size_bytes}

    def _clear_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
