import pathlib
import pytest

from lucid import LucidMainWindow


MODULE_PATH = pathlib.Path(__file__).parent


@pytest.fixture(scope='function')
def main_window(qtbot):
    main_window = LucidMainWindow()
    qtbot.addWidget(main_window)
    return main_window
