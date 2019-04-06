import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QWidget

from lucid import LucidMainWindow


@pytest.fixture(scope='function')
def main_window(qtbot):
    main_window = LucidMainWindow()
    qtbot.addWidget(main_window)
    return main_window


def test_add_multiple_docks(main_window, qtbot):
    first_dock = QDockWidget()
    second_dock = QDockWidget()
    for dock in (first_dock, second_dock):
        qtbot.addWidget(dock)
    main_window.addDockWidget(Qt.RightDockWidgetArea, first_dock)
    assert main_window.dockWidgetArea(first_dock) == Qt.RightDockWidgetArea
    assert first_dock in main_window._docks
    main_window.addDockWidget(Qt.RightDockWidgetArea, second_dock)
    assert main_window.dockWidgetArea(first_dock) == Qt.RightDockWidgetArea
    assert main_window.dockWidgetArea(second_dock) == Qt.RightDockWidgetArea


def test_main_window_find_window(main_window, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dock = QDockWidget()
    qtbot.addWidget(dock)
    dock.setWidget(widget)
    main_window.addDockWidget(Qt.RightDockWidgetArea, dock)
    assert LucidMainWindow.find_window(widget) == main_window


def test_main_window_find_window_with_orphan(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    with pytest.raises(EnvironmentError):
        LucidMainWindow.find_window(widget)


def test_main_window_in_dock(main_window, qtbot):

    @LucidMainWindow.in_dock
    def create_widget():
        widget = QWidget(parent=main_window)
        qtbot.addWidget(widget)
        return widget

    create_widget()
    assert len(main_window._docks) == 1


def test_main_window_in_dock_with_area(main_window, qtbot):

    @LucidMainWindow.in_dock(area=Qt.RightDockWidgetArea)
    def create_widget():
        widget = QWidget(parent=main_window)
        qtbot.addWidget(widget)
        return widget

    create_widget()
    assert len(main_window._docks) == 1


def test_main_window_in_dock_with_orphan(qtbot):

    @LucidMainWindow.in_dock
    def create_widget():
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    widget = create_widget()
    assert widget.isVisible()
