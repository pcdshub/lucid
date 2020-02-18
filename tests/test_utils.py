import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget

from lucid.utils import SnakeLayout, no_device_lazy_load


@pytest.mark.parametrize('direction,shape',
                         ((Qt.Horizontal, (6, 2)),
                          (Qt.Vertical, (2, 6))),
                         ids=('Horizontal', 'Vertical'))
def test_snake_layout_add(qtbot, direction, shape):
    layout = SnakeLayout(6, direction=direction)
    # Create widgets
    widgets = [QWidget() for i in range(12)]
    for widget in widgets:
        layout.addWidget(widget)
        qtbot.addWidget(widget)

    assert (layout.columnCount(), layout.rowCount()) == shape


def test_no_device_lazy_load():
    from ophyd import Device, Component as Cpt

    class TestDevice(Device):
        c = Cpt(Device, suffix='Test')

    dev = TestDevice(name='foo')

    old_val = Device.lazy_wait_for_connection
    assert dev.lazy_wait_for_connection is old_val
    assert dev.c.lazy_wait_for_connection is old_val

    with no_device_lazy_load():
        dev2 = TestDevice(name='foo')

        assert Device.lazy_wait_for_connection is False
        assert dev2.lazy_wait_for_connection is False
        assert dev2.c.lazy_wait_for_connection is False

    assert Device.lazy_wait_for_connection is old_val
    assert dev.lazy_wait_for_connection is old_val
    assert dev.c.lazy_wait_for_connection is old_val
