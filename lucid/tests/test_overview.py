import pytest
from ophyd.sim import SynAxis, motor
from qtpy.QtWidgets import QWidget

from lucid.overview import IndicatorCell


@pytest.fixture(scope='function')
def cell(qtbot):
    cell = IndicatorCell(title='MFX DG2')
    qtbot.addWidget(cell)
    return cell


def test_base_device_button_menu(cell):
    device_count = 12
    for i in range(device_count):
        motor = SynAxis(name=f'motor_{i}')
        cell.add_device(motor)
    cell._menu_shown()
    for device in cell.devices:
        assert device.name in [action.text()
                               for action in cell.device_menu.actions()]


def test_base_device_button_show_device(cell):
    display = cell.show_device(motor)
    assert display.devices[0] == motor
    assert motor.name in cell._device_displays


def test_base_device_button_show_device_repeated(cell, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    cell._device_displays[motor.name] = widget
    cell.show_device(motor)
    assert cell._device_displays[motor.name] == widget


def test_base_device_button_show_all(cell):
    cell.devices = [motor]
    suite = cell.show_all()
    assert suite.devices == [motor]


def test_base_device_button_show_all_repeated(cell):
    cell.devices = [motor]
    suite = cell.show_all()
    cell.show_all()
    assert suite == cell._suite
    assert suite.devices == [motor]


def test_indicator_cell_add_device(cell):
    device_count = 12
    for i in range(device_count):
        motor = SynAxis(name=f'motor_{i}')
        cell.add_device(motor)
    assert len(cell.devices) == 12


def test_indicator_cell_selection(cell):
    cell._devices_shown(True)
    assert cell.selected


def test_indicator_cell_deselection(cell):
    cell._selecting_widgets.append(cell)
    cell._devices_shown(False)
    assert not cell.selected
