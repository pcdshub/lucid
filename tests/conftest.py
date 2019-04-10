import pytest

from lucid import LucidMainWindow


@pytest.fixture(scope='function')
def main_window(qtbot):
    main_window = LucidMainWindow()
    qtbot.addWidget(main_window)
    return main_window
