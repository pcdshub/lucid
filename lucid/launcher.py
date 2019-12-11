def main():
    import argparse
    from qtpy.QtWidgets import QApplication
    from ophyd.sim import SynAxis
    from random import randint
    import typhon
    from . import __version__
    from .main_window import LucidMainWindow
    from .overview import IndicatorGrid

    parser = argparse.ArgumentParser(description="LUCID - LCLS User Control and Interface Design")
    parser.add_argument('--version', action='version',
                    version='LUCID {version}'.format(version=__version__),
                    help="Show LUCID's version number and exit.")

    parser.add_argument(
        'beamline',
        help='Specify the beamline name to compose the home screen.',
        type=str
    )
    parser.add_argument(
        '--toolbar',
        help='Path to the YAML file describing the entries for the Quick'+
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
    lucid_args = parser.parse_args()

    app = QApplication([])

    window = LucidMainWindow()
    typhon.use_stylesheet(dark=True)
    grid = IndicatorGrid()
    # Fill IndicatorGrid
    for stand in ('DIA', 'DG1', 'TFS', 'DG2', 'TAB', 'DET', 'DG3'):
        for system in ('Timing', 'Beam Control', 'Diagnostics', 'Motion',
                       'Vacuum'):
            # Create devices
            device_count = randint(2, 20)
            system_name = system.lower().replace(' ', '_')
            devices = [SynAxis(name=f'{stand.lower()}_{system_name}_{i}')
                       for i in range(device_count)]
            grid.add_devices(devices, stand=stand, system=system)
    window.setCentralWidget(grid)
    window.show()

    app.exec_()


if __name__ == '__main__':
    main()
