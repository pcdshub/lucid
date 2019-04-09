import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QWidget

from lucid import LucidMainWindow


@pytest.fixture(scope='function')
def main_window(qtbot):
    main_window = LucidMainWindow()
    qtbot.addWidget(main_window)
    return main_window


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


def test_main_window_setup_dock(main_window):
    dock = main_window.setup_dock()
    assert main_window.dock_manager is not None


def test_main_window_repeat_setup_dock(main_window):
    dock = main_window.setup_dock()
    assert id(dock) == id(main_window.setup_dock())


def test_main_window_reopen_dock(main_window):
    dock = main_window.setup_dock()
    dock.close()
    assert main_window.dock_manager is None
    dock = main_window.setup_dock()
    assert main_window.dock_manager is not None


def test_main_window_in_dock(main_window, qtbot):
    widget_name = 'my_dock'
    title = 'Test Dock'

    @LucidMainWindow.in_dock(area=Qt.RightDockWidgetArea,
                             title=title)
    def create_widget():
        widget = QWidget(parent=main_window)
        widget.setObjectName(widget_name)
        qtbot.addWidget(widget)
        return widget

    widget = create_widget()

    assert main_window.dock_manager is not None
    dock = main_window.dock_manager.find_dock_widget(widget_name)
    assert dock is not None
    assert dock.widget() == widget


def test_main_window_in_dock_with_orphan(qtbot):

    @LucidMainWindow.in_dock
    def create_widget():
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    widget = create_widget()
    assert widget.isVisible()


def test_main_window_in_dock_repeat(main_window, qtbot):
    # Function to create show QWidget
    widget = QWidget(parent=main_window)
    qtbot.addWidget(widget)
    create_widget = LucidMainWindow.in_dock(lambda: widget)
    # Show widget once
    create_widget()
    dock = widget.parent()
    create_widget()
    assert dock == widget.parent()


@pytest.mark.parametrize('start_floating,close,finish_floating',
                         ((False, False, False),
                          (False, True, False),
                          (True, False, True),
                          (True, False, True)),
                         ids=('in tab', 'closed from tab',
                              'floating', 'closed from floating'))
def test_main_window_raise(main_window, qtbot,
                           start_floating, close, finish_floating):
    # Add our docks
    dock1 = QDockWidget()
    qtbot.addWidget(dock1)
    dock2 = QDockWidget()
    qtbot.addWidget(dock2)
    main_window.addDockWidget(Qt.RightDockWidgetArea, dock1)
    main_window.addDockWidget(Qt.RightDockWidgetArea, dock2)
    # Setup dock
    dock1.setFloating(start_floating)
    if close:
        dock1.close()
    # Re-raise
    main_window.raise_dock(dock1)
    assert dock1.isFloating() == finish_floating
    if not finish_floating:
        assert main_window.tabifiedDockWidgets(dock2) == [dock1]
