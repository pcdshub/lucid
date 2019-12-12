def get_happi_entry_value(entry, key, search_extraneous=True):
    extraneous = entry.extraneous
    value = getattr(entry, key, None)
    if value is None and search_extraneous:
        # Try to look at extraneous
        value = extraneous.get(key, None)

    if not value:
        raise ValueError('Invalid Key for Device.')
    return value


def main():
    import logging
    import argparse
    from qtpy.QtWidgets import QApplication
    import happi
    import typhon
    from . import __version__
    from .main_window import LucidMainWindow
    from .overview import IndicatorGrid

    proj_desc = "LUCID - LCLS User Control and Interface Design"
    parser = argparse.ArgumentParser(description=proj_desc)
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

    lucid_args = parser.parse_args()

    logger = logging.getLogger('')
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(lucid_args.log_level)
    handler.setLevel(lucid_args.log_level)

    app = QApplication([])

    window = LucidMainWindow()
    typhon.use_stylesheet(dark=True)
    grid = IndicatorGrid()

    if lucid_args.beamline != 'DEMO':
        # Fill with Data from Happi
        cli = happi.Client.from_config()
        devices = cli.search(beamline=lucid_args.beamline)

        for dev in devices:
            try:
                stand = get_happi_entry_value(dev, lucid_args.row_group_key)
                system = get_happi_entry_value(dev, lucid_args.col_group_key)
                dev_obj = [happi.loader.from_container(dev)]
                grid.add_devices(dev_obj, stand=stand, system=system)
            except ValueError as ex:
                print(ex)
                continue

    else:
        # Fill with random fake simulated devices
        from random import randint
        from ophyd.sim import SynAxis

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
