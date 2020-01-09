import logging
import re

import happi
import fuzzywuzzy.fuzz

from pydm.widgets import PyDMDrawingCircle
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGridLayout
from typhon import TyphonDeviceDisplay, TyphonSuite

logger = logging.getLogger(__name__)

HAPPI_GENERAL_SEARCH_KEYS = ('name', 'prefix', 'stand')


class SnakeLayout(QGridLayout):
    """
    Snaking Layout

    The size is the maximum number of widgets before beginning the next row or
    column. The direction specifies whether the grid pattern will be filled
    column first, or row first.

    Parameters
    ----------
    widgets: Iterable
        List of widgets to place in grid

    size: int
        Maximum size of row or column

    direction: Qt.Direction, optional
        Whether the layout is filled column or row first.

    Returns
    -------
    QGridLayout
        Filled with widgets provided in function call

    Example
    -------
    .. code:: python

        # Three rows
        gridify(widgets, 3, direction=Qt.Vertical)

        # Five columns
        gridify(widgets, 5, direction=Qt.Vertical)  # Default direction

    """
    def __init__(self, size, direction=Qt.Horizontal):
        super().__init__()
        self.size = int(size)
        self.direction = direction

    def addWidget(self, widget):
        """Add a QWidget to the layout"""
        # Number of widgets already existing
        position = self.count()
        # Desired position based on current count
        grid_position = [position / self.size, position % self.size]
        # Start vertically if desired
        if self.direction == Qt.Vertical:
            grid_position.reverse()
        # Add to layout
        super().addWidget(widget,
                          grid_position[0],
                          grid_position[1])


def indicator_for_device(device):
    """Create a QWidget to indicate the alarm state of a QWidget"""
    # This is a placeholder. There will be a system for determining the mapping
    # of Device to icon put in place
    circle = PyDMDrawingCircle()
    circle.setStyleSheet('PyDMDrawingCircle '
                         '{border: none; '
                         ' background: transparent;'
                         ' qproperty-penColor: black;'
                         ' qproperty-penWidth: 2;'
                         ' qproperty-penStyle: SolidLine;'
                         ' qproperty-brush: rgba(0,220,0,120);} ')
    return circle


def display_for_device(device, display_type=None):
    """Create a TyphonDeviceDisplay for a given device"""
    logger.debug("Creating device display for %r", device)
    display = TyphonDeviceDisplay.from_device(device)
    if display_type:
        display.display_type = display_type
    return display


def suite_for_devices(devices, *, parent=None):
    """Create a TyphonSuite to display multiple devices"""
    suite = TyphonSuite(parent=parent)
    for device in devices:
        suite.add_device(device)
    return suite


def fuzzy_match(a, b, *, case_insensitive=True, threshold=50):
    'Fuzzy matching of strings `a` and `b`, with some LUCID-specific tweaks'
    if case_insensitive:
        a = a.lower()
        b = b.lower()

    ratio = fuzzywuzzy.fuzz.ratio(a, b)
    if ratio >= threshold:
        return ratio

    # Special case a few scenarios, returning a value just at the threshold
    # of interest:
    # * 'VGC1' should match 'vgc_1' - ignore underscores and check if the
    #   string is in
    # * 'abc' should match 'xyz abc123' - despite the low fuzzing similarity
    # * 'abc' should match 'xyz 123 abc' - despite the low fuzzing similarity,
    #   and with a score better than the previous
    # TODO: there are very likely better ways of doing this
    for ignore_char in [None, '_']:
        for s1, s2 in [(a, b), (b, a)]:
            if ignore_char:
                s1 = s1.replace(ignore_char, '')
                s2 = s2.replace(ignore_char, '')

            if len(s1) > len(s2) > 2:
                if s1.endswith(s2) or s1.startswith(s2):
                    return threshold + 1
                if s1 in s2:
                    return threshold
    return ratio


_HAPPI_CLIENT = None


def get_happi_client():
    '''
    Create and cache a happi client from configuration
    '''
    global _HAPPI_CLIENT
    if _HAPPI_CLIENT is None:
        _HAPPI_CLIENT = happi.Client.from_config()
    return _HAPPI_CLIENT


def find_ancestor_widget(widget, cls):
    'Find an ancestor of `widget` given its class `cls`'
    while widget is not None:
        if isinstance(widget, cls):
            return widget
        widget = widget.parent()


SEARCH_PATTERN = re.compile(
    r'((?P<category>[a-z_][a-z0-9_]*):\s*)?(?P<text>[^ ]+)',
    re.VERBOSE | re.IGNORECASE
)


def split_search_pattern(text):
    '''
    Split search pattern into (optional) categories
    Patterns are space-delimited, with each entry as follows:
        category_name: text_to_match_in_category
        text_to_match_generally
    '''

    matches = list(m.groupdict()
                   for m in SEARCH_PATTERN.finditer(text.strip())
                   )
    by_category = [
        (m['category'], m['text'])
        for m in matches if m['category'] is not None
    ]

    general = [
        m['text']
        for m in matches if m['category'] is None
    ]

    if general:
        general.append(' '.join(general))

    return by_category, general
