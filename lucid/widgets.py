"""Utility widgets"""
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDockWidget


class QDockWidget(QDockWidget):
    """QDockWidget that emits a closing Signal"""
    closed = Signal()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()
