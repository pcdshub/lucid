from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from lucid.main_window import LucidMainWindow


@pytest.fixture(scope="function")
def main_window(qtbot: QtBot) -> LucidMainWindow:
    main_window = LucidMainWindow(beamline="pytest", toolbar=str(Path(__file__).parent / "TST_toolbar.yaml"))
    main_window.resize(main_window.width_threshold + 100, main_window.height())
    qtbot.addWidget(main_window)
    return main_window


def test_finalize_window_settings_smoke(main_window: LucidMainWindow):
    main_window.finalize_window_settings()


def test_dock_visibility(main_window: LucidMainWindow, qtbot: QtBot):
    def dock_not_visible():
        assert not main_window.dock.isVisible()

    def dock_is_visible():
        assert not main_window.dock.isVisible()

    main_window.resize(main_window.width_threshold - 100, main_window.height())
    qtbot.waitUntil(dock_not_visible, timeout=1000)
    dock_not_visible()
    main_window.resize(main_window.width_threshold + 100, main_window.height())
    qtbot.waitUntil(dock_is_visible, timeout=1000)
    dock_is_visible()


def test_default_dock_widget(main_window: LucidMainWindow):
    assert main_window.dock.tab_widgets[0][0].currentWidget().windowTitle() == "DOCK2"
