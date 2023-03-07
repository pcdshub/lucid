import os

import typhos.utils
from qtpy import QtCore, QtGui, QtWidgets


class Splash(QtWidgets.QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)

        self._base_path = os.path.dirname(os.path.abspath(__file__))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        logo_pixmap = QtGui.QPixmap(os.path.join(self._base_path, 'logo.png'))
        logo_pixmap = logo_pixmap.scaled(400, 100, 1)

        logo = QtWidgets.QLabel(self)
        logo.setPixmap(logo_pixmap)
        layout.addWidget(logo)

        self.status_display = QtWidgets.QLabel()
        tout = typhos.utils.TyphosLoading.LOADING_TIMEOUT_MS
        # No Timeout!
        typhos.utils.TyphosLoading.LOADING_TIMEOUT_MS = -1
        loading = typhos.utils.TyphosLoading(self)
        typhos.utils.TyphosLoading.LOADING_TIMEOUT_MS = tout

        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.status_display)
        status_layout.addWidget(loading)

        layout.addLayout(status_layout)

    def update_status(self, msg):
        self.status_display.setText(f"Loading: {msg}")
        QtWidgets.QApplication.instance().processEvents()
