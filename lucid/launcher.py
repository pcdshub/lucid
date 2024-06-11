import asyncio
import collections
import functools
import logging
import pathlib
import random
import signal

import happi  # noqa
import pcdsutils.log
import typhos
import typhos.utils
from ophyd.signal import EpicsSignalBase
from pydm import exception
from qtpy import QtCore, QtWidgets

import lucid

from . import utils
from .dock_shim import ads

MODULE_PATH = pathlib.Path(__file__).parent

logger = logging.getLogger(__name__)


def get_happi_entry_value(entry, key):
    value = entry.metadata.get(key, None)
    if not value:
        raise ValueError(f'Invalid Key ({key} not in {entry}.')
    return value


def get_parser():
    import argparse

    from . import __version__

    proj_desc = "LUCID - LCLS User Control and Interface Design"
    parser = argparse.ArgumentParser(description=proj_desc)
    parser.add_argument('--version', action='version',
                        version=f'LUCID {__version__}',
                        help="Show LUCID's version number and exit.")

    parser.add_argument(
        'beamline',
        help='Specify the beamline name to compose the home screen.',
        type=str,
        nargs='+'
    )
    parser.add_argument(
        '--toolbar',
        help='Path to the YAML file describing the entries for the Quick' +
             ' Access Toolbar.',
        default=None,
        required=False,
        type=argparse.FileType('r', encoding='UTF-8')
    )
    parser.add_argument(
        '--row_group_key',
        help='The Happi field to use for row grouping.',
        default='location_group',
        required=False
    )
    parser.add_argument(
        '--col_group_key',
        help='The Happi field to use for column grouping.',
        default='functional_group',
        required=False
    )
    parser.add_argument(
        '--log_level',
        help='Configure level of log display',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO'
    )
    parser.add_argument(
        '--dark',
        help='Use dark Stylesheet',
        action='store_true',
        default=False
    )
    parser.add_argument(
        '--skip_happi',
        help='Skip loading entries from happi',
        action='store_true',
        default=False
    )
    return parser


def parse_arguments(*args, **kwargs):
    parser = get_parser()
    return parser.parse_args(*args, **kwargs)


class HappiLoader(QtCore.QThread):
    def __init__(self, *args, beamline, group_keys, callbacks, **kwargs):
        self.beamline = beamline
        self.group_keys = group_keys
        self.callbacks = callbacks
        super().__init__(*args, **kwargs)

    def _load_from_happi(self, row_group_key, col_group_key):
        '''Fill with Data from Happi'''
        cli = lucid.utils.get_happi_client()
        results = []
        for line in self.beamline:
            results += cli.search(beamline=line, active=True)

        dev_groups = collections.defaultdict(list)

        if not len(results):
            raise ValueError(
                f"Could not find entries for beamline {self.beamline}")

        with typhos.utils.no_device_lazy_load():
            for res in results:
                try:
                    stand = get_happi_entry_value(res, row_group_key)
                    system = get_happi_entry_value(res, col_group_key)
                    dev_obj = res.get(threaded=True)
                    dev_groups[f"{stand}|{system}"].append(dev_obj)
                except Exception:
                    logger.exception('Failed to load device %s', res)
                    continue
        return dev_groups

    def _load_demo(self):
        '''Fill with random fake simulated devices'''
        from ophyd.sim import SynAxis

        # Create an event loop in this thread for ophyd.sim
        asyncio.set_event_loop(asyncio.new_event_loop())
        dev_groups = collections.defaultdict(list)

        # Fill IndicatorGrid
        for stand in ('DIA', 'DG1', 'TFS', 'DG2', 'TAB', 'DET', 'DG3'):
            for system in ('Timing', 'Beam Control', 'Diagnostics',
                           'Motion', 'Vacuum'):
                # Create devices
                device_count = random.randint(1, 12)
                # device_count = 1
                system_name = system.lower().replace(' ', '_')
                devices = [
                    SynAxis(name=f'{stand.lower()}_{system_name}_{i}')
                    for i in range(device_count)]
                dev_groups[f"{stand}|{system}"] = devices
        return dev_groups

    def run(self):
        exc = None
        row_group_key, col_group_key = self.group_keys

        dev_groups = None

        try:
            if self.beamline != 'DEMO':
                dev_groups = self._load_from_happi(row_group_key,
                                                   col_group_key)
            else:
                dev_groups = self._load_demo()
        except Exception as e:
            exc = e

        # Call the callback using the Receiver Slot Thread
        for cb in self.callbacks:
            f = functools.partial(cb, devices=dev_groups)
            QtCore.QTimer.singleShot(0, f)

        # This will be grabbed by the uncaught exception handler
        if exc:
            raise exc


class NoOpLoader(QtCore.QThread):
    def run(self):
        return


def launch(beamline, *, toolbar=None, row_group_key="location_group",
           col_group_key="functional_group", log_level="INFO",
           dark=False, skip_happi=False):
    # Re-enable sigint (usually blocked by pyqt)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Silence the logger from pyPDB.dbd.yacc
    logging.getLogger("pyPDB.dbd.yacc").setLevel(logging.WARNING)
    logging.getLogger("ophyd").setLevel(logging.WARNING)

    lucid_logger = logging.getLogger('')
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] - %(message)s')
    handler.setFormatter(formatter)
    lucid_logger.addHandler(handler)
    lucid_logger.setLevel(log_level)
    handler.setLevel(log_level)
    pcdsutils.log.PydmDemotionFilter.install(only_duplicates=False)

    app = QtWidgets.QApplication([])
    app.setOrganizationName("SLAC National Accelerator Laboratory")
    app.setOrganizationDomain("slac.stanford.edu")
    app.setApplicationName("LUCID")

    typhos.use_stylesheet(dark=dark)

    splash = lucid.splash.Splash()
    splash.show()

    splash.update_status("Creating Main Window")
    window = lucid.main_window.LucidMainWindow(dark=dark)
    window.setWindowTitle(f"LUCID - {beamline}")

    # Configure centralized PCDS logging:
    if utils.centralized_logging_enabled():
        pcdsutils.log.configure_pcds_logging()

    # Install exception hook handler with dialog popup
    exception.install(use_default_handler=False)
    # Use custom exception handler
    exception.ExceptionDispatcher().newException.connect(window.handle_error)

    grid = lucid.overview.IndicatorGridWithOverlay(toolbar_file=toolbar)

    splash.update_status(f"Loading {beamline} devices")

    # callback list for Happi Loader
    cbs = [grid.add_from_dict]
    if skip_happi:
        loader = NoOpLoader()
    else:
        loader = HappiLoader(beamline=beamline,
                             group_keys=(row_group_key, col_group_key),
                             callbacks=cbs)

    def grid_to_dock():
        dock_widget = ads.CDockWidget('Grid')
        dock_widget.setToggleViewActionMode(ads.CDockWidget.ActionModeShow)
        dock_widget.setFeature(dock_widget.DockWidgetClosable, False)
        dock_widget.setFeature(dock_widget.DockWidgetFloatable, False)
        dock_widget.setFeature(dock_widget.DockWidgetMovable, False)
        dock_widget.setMinimumSizeHintMode(
            ads.CDockWidget.MinimumSizeHintFromContent
        )
        dock_widget.setWidget(grid.frame,
                              ads.CDockWidget.eInsertMode.ForceNoScrollArea)

        window.dock_manager.addDockWidget(ads.LeftDockWidgetArea,
                                          dock_widget)

    loader.finished.connect(splash.accept)
    loader.finished.connect(grid_to_dock)
    loader.finished.connect(window.show)

    loader.start()

    app.exec_()


def main():
    args = parse_arguments()
    kwargs = vars(args)
    # TODO make configurable
    timeout = 10
    EpicsSignalBase.set_defaults(
        timeout=timeout,
        connection_timeout=timeout,
    )
    launch(**kwargs)


if __name__ == "__main__":
    main()
