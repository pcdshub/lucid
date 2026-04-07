import pytest
from pytestqt.qtbot import QtBot

from lucid.dock import LucidDock


@pytest.fixture(scope="function")
def lucid_dock(qtbot: QtBot) -> LucidDock:
    dock = LucidDock()
    dock.show()
    qtbot.addWidget(dock)
    return dock
