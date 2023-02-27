from unittest.mock import Mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QWidget

from lucid import LucidMainWindow


@pytest.fixture(scope='function')
def main_window():
    main_window = LucidMainWindow()
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
    assert main_window.dock_manager is not None


def test_main_window_in_dock(main_window, qtbot):
    widget_name = 'my_dock'
    title = 'Test Dock'

    @LucidMainWindow.in_dock(area=Qt.RightDockWidgetArea,
                             title=title)
    def create_widget():
        widget = QWidget()
        widget.setObjectName(widget_name)
        return widget

    widget = create_widget()

    assert main_window.dock_manager is not None
    dock = main_window.dock_manager.find_dock_widget_by_title(title)
    assert dock is not None
    assert dock.widget() == widget


def test_main_window_in_dock_active_slot(main_window, qtbot):
    with qtbot.wait_exposed(main_window):
        main_window.show()
    # Function to create show QWidget
    widget = QWidget()
    cb = Mock()
    create_widget = LucidMainWindow.in_dock(func=lambda: widget,
                                            active_slot=cb)
    create_widget()
    assert cb.called
    cb.assert_called_with(True)
    with qtbot.waitSignal(widget.parent().closed):
        widget.parent().toggleView(False)
    cb.assert_called_with(False)


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
    # main_window.raise_dock(dock1)
    assert dock1.isFloating() == finish_floating
    # TODO
    # if not finish_floating:
    #     assert main_window.tabifiedDockWidgets(dock2) == [dock1]
