Lucid Grid Configuration
========================

``lucid``'s main grid area is an auto-generated series of buttons and indicators,
where each indicator represents a device
loaded from a ``happi`` database.

.. figure:: /_static/lucid_grid.png
   :scale: 50 %
   :alt: Lucid display with the grid highlighted.


Which Devices are Included?
---------------------------

When ``lucid`` is invoked, the only required argument is the positional ``beamline`` argument.
This argument is used as a ``happi`` search term to fill the grid.

This is equivalent to the following search using the ``happi`` command line,
assuming your beamline is named BEAMLINE:

.. code-block:: bash

    happi search beamline=BEAMLINE active=True


All devices that match this search and load without errors will be included in the grid.
All other devices will be excluded.
The search is case-sensitive.

Note that inactive devices are not included,
and that this only targets happi entries that have a beamline associated with them at all.
This requires the ``happi`` containers defined in ``pcdsdevices``,
which define the ``beamline`` field.

Note: if you prefer not to load any devices, you can skip this step by passing
a command-line parameter:

.. code-block:: bash

    lucid --skip_happi MY_BEAMLINE


How are the Devices Arranged in the Grid?
-----------------------------------------

The grid is defined by the various metadata values found in the ``happi`` database.
The default metadata keys in use are:

- ``location_group``, to select which column to put a device into
- ``functional_group``, to select with row to put a device into

That is to say, by default we expect the row headers on the left to be functional names like
"imager" or "vacuum" and column headers on the top to be location names like "Section 01" or "Section 02".

You can change which metadata keys are used by passing the
``--row_group_key`` and ``--col_group_key`` command-line parameters
to select the row grouping and column groupings respectively.

Each unique string (case-sensitive) found in the group key metadata for the
active devices will create an additional row or column in the grid
with the corresponding header text.
The rows and the columns will each be sorted in alphabetical order.

Each device indicator will be added to a single square cell in the grid that
corresponds with its metadata sorting.

This provides the following features:

- An alarm indicator that represents the device's worst alarm state,
  with mouseover text that will show more precise information
- The option to click the cell and select the device name to open the device's
  ``typhos`` screen in the right-hand dock area
- The option to click the row or column header to select the device name for the
  same purpose as above, where the devices can be from any cell in the corresponding
  row or column.
- The ability to search for devices within the grid using the search bar,
  which will highlight their indicators in the grid view.


Limitations
-----------

- There are currently no configuration options for row/column ordering or
  customization of the happi search used to accumulate devices.
- The only way to adjust the grid is to carefully manipulate the ``happi`` database.
- There are no options for changing the sizes of cells or the sizes of the alarm
  indicators held inside the cells.
