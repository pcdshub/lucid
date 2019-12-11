def main():
    from qtpy.QtWidgets import QApplication
    from ophyd.sim import SynAxis
    from random import randint
    import typhon
    from .main_window import LucidMainWindow
    from .overview import IndicatorGrid

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
