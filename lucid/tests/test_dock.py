from pathlib import Path
from unittest.mock import Mock

import pytest
from pytestqt.qtbot import QtBot
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QWidget

import lucid.dock
from lucid.dock import LucidDock, LucidDockButton


@pytest.fixture(scope="function")
def lucid_dock(qtbot: QtBot) -> LucidDock:
    dock = LucidDock()
    dock.show()
    qtbot.addWidget(dock)
    return dock


@pytest.fixture(scope="function")
def dock_button(qtbot: QtBot) -> LucidDockButton:
    button = LucidDockButton()
    qtbot.addWidget(button)
    return button


def test_add_to_dock_user_keybinds(lucid_dock: LucidDock, monkeypatch: pytest.MonkeyPatch, qtbot: QtBot):
    # Mock our own methods to check if they got called
    add_to_dock_mock = Mock()
    open_in_new_window_mock = Mock()
    monkeypatch.setattr(LucidDock, "add_to_dock", add_to_dock_mock)
    monkeypatch.setattr(LucidDock, "open_in_new_window", open_in_new_window_mock)

    def reset_mocks():
        add_to_dock_mock.reset_mock()
        open_in_new_window_mock.reset_mock()

    title = "title"
    widget = QWidget()
    qtbot.addWidget(widget)

    def add_to_dock():
        LucidDock.add_to_dock_user_keybinds(title=title, widget=widget)

    # Standard: open in dock
    reset_mocks()
    add_to_dock()
    add_to_dock_mock.assert_called_once_with(title=title, widget=widget, new_tab=False)
    open_in_new_window_mock.assert_not_called()

    # Dock hidden: open in new window
    reset_mocks()
    lucid_dock.hide()
    add_to_dock()
    add_to_dock_mock.assert_not_called()
    open_in_new_window_mock.assert_called_once_with(title=title, widget=widget)
    lucid_dock.show()

    # Ctrl pressed: open in dock in a new tab
    monkeypatch.setattr(lucid.dock, "ctrl_pressed", lambda: True)
    monkeypatch.setattr(lucid.dock, "shift_pressed", lambda: False)
    reset_mocks()
    add_to_dock()
    add_to_dock_mock.assert_called_once_with(title=title, widget=widget, new_tab=True)
    open_in_new_window_mock.assert_not_called()

    # Shift pressed: open in new window
    monkeypatch.setattr(lucid.dock, "ctrl_pressed", lambda: False)
    monkeypatch.setattr(lucid.dock, "shift_pressed", lambda: True)
    reset_mocks()
    add_to_dock()
    add_to_dock_mock.assert_not_called()
    open_in_new_window_mock.assert_called_once_with(title=title, widget=widget)


def test_add_to_dock(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)
    widget2 = QWidget()
    qtbot.add_widget(widget2)

    tab_widget = lucid_dock.tab_widgets[0][0]

    LucidDock.add_to_dock(title="", widget=widget1)
    assert tab_widget.currentWidget() is widget1
    assert tab_widget.count() == 1

    LucidDock.add_to_dock(title="", widget=widget2)
    assert tab_widget.currentWidget() is widget2
    assert tab_widget.count() == 1

    LucidDock.add_to_dock(title="", widget=widget1, new_tab=True)
    assert tab_widget.currentWidget() is widget1
    assert tab_widget.count() == 2


def test_detach_from_dock(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)

    tab_widget = lucid_dock.tab_widgets[0][0]

    lucid_dock.add_to_dock(title="", widget=widget1)
    lucid_dock.detach_from_dock(tab_widget=tab_widget)

    assert tab_widget.currentWidget() is None
    assert tab_widget.count() == 0

    assert widget1.parent() is None
    assert widget1.isVisible()
    assert widget1 in lucid_dock.detached_widgets


def test_open_in_new_window(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)

    LucidDock.open_in_new_window(title="", widget=widget1)

    tab_widget = lucid_dock.tab_widgets[0][0]

    assert tab_widget.currentWidget() is None
    assert tab_widget.count() == 0

    assert widget1.parent() is None
    assert widget1.isVisible()
    assert widget1 in lucid_dock.detached_widgets


def test_reattach_user_choice(lucid_dock: LucidDock, monkeypatch: pytest.MonkeyPatch, qtbot: QtBot):
    # Mock our own methods to check if they got called
    reattach_to_dock_mock = Mock()
    show_attach_menu_mock = Mock()
    monkeypatch.setattr(LucidDock, "reattach_to_dock", reattach_to_dock_mock)
    monkeypatch.setattr(LucidDock, "show_attach_menu", show_attach_menu_mock)

    tab_widget = lucid_dock.tab_widgets[0][0]

    def reset_mocks():
        reattach_to_dock_mock.reset_mock()
        show_attach_menu_mock.reset_mock()

    reset_mocks()
    lucid_dock.reattach_user_choice(tab_widget=tab_widget)
    reattach_to_dock_mock.assert_not_called()
    show_attach_menu_mock.assert_not_called()

    widget1 = QWidget()
    qtbot.add_widget(widget1)

    LucidDock.open_in_new_window(title="", widget=widget1)
    reset_mocks()
    lucid_dock.reattach_user_choice(tab_widget=tab_widget)
    reattach_to_dock_mock.assert_called_once_with(widget=widget1, tab_widget=tab_widget)
    show_attach_menu_mock.assert_not_called()

    widget2 = QWidget()
    qtbot.add_widget(widget2)

    LucidDock.open_in_new_window(title="", widget=widget2)
    reset_mocks()
    lucid_dock.reattach_user_choice(tab_widget=tab_widget)
    reattach_to_dock_mock.assert_not_called()
    show_attach_menu_mock.assert_called_once_with(tab_widget=tab_widget, pos=QCursor().pos())


def test_reattach_to_dock(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)

    tab_widget = lucid_dock.tab_widgets[0][0]

    LucidDock.open_in_new_window(title="", widget=widget1)
    lucid_dock.reattach_to_dock(widget=widget1, tab_widget=tab_widget)

    assert widget1 not in lucid_dock.detached_widgets
    assert tab_widget.currentWidget() is widget1
    assert tab_widget.count() == 1

    widget2 = QWidget()
    qtbot.add_widget(widget2)

    LucidDock.open_in_new_window(title="", widget=widget2)
    lucid_dock.reattach_to_dock(widget=widget2, tab_widget=tab_widget)

    assert widget2 not in lucid_dock.detached_widgets
    assert tab_widget.currentWidget() is widget2
    assert tab_widget.count() == 2


def test_show_attach_menu(lucid_dock: LucidDock, qtbot: QtBot):
    tab_widget = lucid_dock.tab_widgets[0][0]

    widgets = [QWidget() for _ in range(3)]
    for num, wd in enumerate(widgets):
        qtbot.add_widget(wd)
        LucidDock.open_in_new_window(title=f"{num}", widget=wd)
        assert wd in lucid_dock.detached_widgets

    menu = lucid_dock.show_attach_menu(tab_widget=tab_widget)
    for action in menu.actions():
        action.trigger()
        this_widget = widgets[int(action.text())]
        qtbot.wait_signal(action.triggered)
        assert this_widget not in lucid_dock.detached_widgets
        assert tab_widget.currentWidget() is this_widget

    assert tab_widget.count() == 3


def test_clean_detached_widgets(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)

    LucidDock.open_in_new_window(title="", widget=widget1)
    assert widget1 in lucid_dock.detached_widgets

    widget1.close()

    def not_vis():
        assert not widget1.isVisible()

    qtbot.wait_until(not_vis)

    lucid_dock.clean_detached_widgets()
    assert not lucid_dock.detached_widgets


def test_not_clean_minimized_widgets(lucid_dock: LucidDock, qtbot: QtBot):
    widget1 = QWidget()
    qtbot.add_widget(widget1)

    LucidDock.open_in_new_window(title="", widget=widget1)
    assert widget1 in lucid_dock.detached_widgets

    widget1.showMinimized()

    def is_minim():
        assert widget1.isMinimized()

    qtbot.wait_until(is_minim)

    lucid_dock.clean_detached_widgets()
    assert widget1 in lucid_dock.detached_widgets


def test_build_widget(dock_button: LucidDockButton):
    dock_button.setFilename("lucid/tests/dock1.ui")
    widget1 = dock_button.build_widget()
    assert widget1.windowTitle() == "DOCK1"
    widget2 = dock_button.build_widget()
    assert widget1 is widget2


def test_build_widget_ui_edited(dock_button: LucidDockButton, tmp_path: Path):
    local_ui = Path(__file__).parent / "dock1.ui"
    temp_ui = tmp_path / "dock1.ui"

    with open(local_ui, "r") as fd:
        original_text = fd.read()

    with open(temp_ui, "w") as fd:
        fd.write(original_text)

    dock_button.setFilename(str(temp_ui))
    widget1 = dock_button.build_widget()
    assert widget1.windowTitle() == "DOCK1"

    new_text = original_text.replace("DOCK1", "NEW_EDIT")

    with open(temp_ui, "w") as fd:
        fd.write(new_text)

    widget2 = dock_button.build_widget()
    assert widget1 is not widget2
    assert widget2.windowTitle() == "NEW_EDIT"


def test_multidock(lucid_dock: LucidDock, qtbot: QtBot):
    widgets = [QWidget() for _ in range(7)]
    for widget in widgets:
        qtbot.add_widget(widget)

    lucid_dock.dock_columns_spinbox.setValue(3)
    lucid_dock.dock_rows_spinbox.setValue(2)
    lucid_dock.apply_settings()

    # 6 docks, we should fill them in order and then replace the first one
    lucid_dock.add_to_dock(widgets[0], "")
    assert lucid_dock.tab_widgets[0][0].currentWidget() is widgets[0]
    lucid_dock.add_to_dock(widgets[1], "")
    assert lucid_dock.tab_widgets[0][1].currentWidget() is widgets[1]
    lucid_dock.add_to_dock(widgets[2], "")
    assert lucid_dock.tab_widgets[0][2].currentWidget() is widgets[2]
    lucid_dock.add_to_dock(widgets[3], "")
    assert lucid_dock.tab_widgets[1][0].currentWidget() is widgets[3]
    lucid_dock.add_to_dock(widgets[4], "")
    assert lucid_dock.tab_widgets[1][1].currentWidget() is widgets[4]
    lucid_dock.add_to_dock(widgets[5], "")
    assert lucid_dock.tab_widgets[1][2].currentWidget() is widgets[5]
    lucid_dock.add_to_dock(widgets[6], "")
    assert lucid_dock.tab_widgets[0][0].currentWidget() is widgets[6]

    # We should be able to move a widget from dock 2 to dock 4
    assert widgets[1] not in lucid_dock.detached_widgets
    lucid_dock.detach_from_dock(lucid_dock.tab_widgets[0][1])
    assert widgets[1] in lucid_dock.detached_widgets
    assert lucid_dock.tab_widgets[0][1].currentWidget() is not widgets[1]
    lucid_dock.reattach_to_dock(widgets[1], lucid_dock.tab_widgets[1][1])
    assert widgets[1] not in lucid_dock.detached_widgets
    assert lucid_dock.tab_widgets[1][1].currentWidget() is widgets[1]
