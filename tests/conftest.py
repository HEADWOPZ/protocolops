from __future__ import annotations

from pathlib import Path

import pytest

from protocolops.config import load_settings

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path):
    return load_settings().model_copy(
        update={
            "mock": True,
            "docs_path": str(REPO / "fixtures" / "docs"),
            "fixtures_dir": str(REPO / "fixtures"),
            "output_dir": str(tmp_path / "output"),
            "ga4_enabled": False,
            "telegram_bot_token": None,
            "telegram_chat_id": None,
        }
    )
