from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from lucid.dock import LucidDock

TESTS_DIR = Path(__file__).parent.resolve()


@pytest.fixture(scope="function")
def lucid_dock(qtbot: QtBot) -> LucidDock:
    dock = LucidDock()
    dock.show()
    qtbot.addWidget(dock)
    return dock
