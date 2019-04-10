import pytest

from ophyd.sim import SynAxis, motor
from qtpy.QtWidgets import QWidget
from typhon import TyphonSuite

from lucid.overview import IndicatorCell


@pytest.fixture(scope='function')
def cell(qtbot):
    cell = IndicatorCell(title='MFX DG2')
    qtbot.addWidget(cell)
    return cell


def test_indicator_cell_add_device(cell):
    device_count = 12
    for i in range(device_count):
        motor = SynAxis(name=f'motor_{i}')
        cell.add_device(motor)
    assert len(cell.devices) == 12
    for device in cell.devices:
        assert device.name in [action.text()
                               for action in cell.device_menu.actions()]


def test_indicator_cell_show_device(cell):
    cell.add_device(motor)
    action = cell.device_menu.actions()[0]
    action.trigger()
    assert motor.name in cell._device_displays


def test_indicator_cell_show_device_repeated(cell, qtbot):
    cell.add_device(motor)
    action = cell.device_menu.actions()[0]
    widget = QWidget()
    qtbot.addWidget(widget)
    cell._device_displays[motor.name] = widget
    action.trigger()
    assert cell._device_displays[motor.name] == widget


def test_indicator_cell_show_devices(cell):
    cell.add_device(motor)
    suite = cell.show_devices()
    assert suite.devices == [motor]


def test_indicator_cell_show_devices_repeated(cell):
    cell.add_device(motor)
    suite = TyphonSuite(parent=cell)
    cell._suite = suite
    cell.show_devices()
    assert suite == cell._suite
    assert suite.devices == [motor]
