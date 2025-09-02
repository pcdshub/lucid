import functools
import logging
import os
import pathlib
import re
import socket
import time
import uuid

import fuzzywuzzy.fuzz
import happi
import pcdsutils.log
from pydm.widgets import PyDMDrawingCircle
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QGridLayout
from typhos import TyphosDeviceDisplay, TyphosSuite
from typhos.utils import no_device_lazy_load

try:
    from typhos.alarm import TyphosAlarmCircle
except ImportError:
    # Compatibility with older versions of typhos
    TyphosAlarmCircle = None


logger = logging.getLogger(__name__)

HAPPI_GENERAL_SEARCH_KEYS = ('name', 'prefix', 'stand')
_HAPPI_CACHE = None
HAPPI_CACHE_UPDATE_PERIOD = 60 * 30
NO_LOG_EXCEPTIONS = (KeyboardInterrupt, SystemExit)
LOG_DOMAINS = {".pcdsn", ".slac.stanford.edu"}
SCREENSHOT_DIR = pathlib.Path(os.environ.get("LUCID_SCREENSHOT_DIR", "/tmp"))


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
        grid_position = [position // self.size, position % self.size]
        # Start vertically if desired
        if self.direction == Qt.Vertical:
            grid_position.reverse()
        # Add to layout
        super().addWidget(widget,
                          grid_position[0],
                          grid_position[1])


if TyphosAlarmCircle is not None:
    def indicator_for_device(device):
        """Create a QWidget to indicate the alarm state of a QWidget"""
        try:
            hints = device.hints['fields']
        except (AttributeError, KeyError):
            hints = []
        circle = TyphosAlarmCircle()
        if hints:
            circle.kindLevel = TyphosAlarmCircle.KindLevel.HINTED
        else:
            circle.kindLevel = TyphosAlarmCircle.KindLevel.NORMAL
        circle.add_device(device)
        return circle
else:
    def indicator_for_device(device):
        """Create a QWidget to indicate the alarm state of a QWidget"""
        # This is a placeholder if a new version of typhos with alarm support
        # is unavailable.
        circle = PyDMDrawingCircle()
        circle.setStyleSheet(
            "PyDMDrawingCircle "
            "{border: none; "
            " background: transparent;"
            " qproperty-penColor: black;"
            " qproperty-penWidth: 2;"
            " qproperty-penStyle: SolidLine;"
            " qproperty-brush: rgba(82,101,244,255);} "
        )
        return circle


def display_for_device(device, display_type=None):
    """Create a TyphosDeviceDisplay for a given device"""
    with no_device_lazy_load():
        logger.debug("Creating device display for %r", device)
        display = TyphosDeviceDisplay.from_device(device, scroll_option="scrollbar")
        if display_type:
            display.display_type = display_type
    return display


def suite_for_devices(devices, *, parent=None, **kwargs):
    """Create a TyphosSuite to display multiple devices"""
    with no_device_lazy_load():
        suite = TyphosSuite(parent=parent, **kwargs)
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


def get_happi_device_cache():
    'Cache all happi device containers as dictionaries'
    global _HAPPI_CACHE

    def check_stale_cache():
        return (time.monotonic() - _HAPPI_CACHE[0]) > HAPPI_CACHE_UPDATE_PERIOD

    if _HAPPI_CACHE is None or check_stale_cache():
        logger.debug('Updating happi cache')
        client = get_happi_client()
        _HAPPI_CACHE = (time.monotonic(), list(client.search()))

    return _HAPPI_CACHE[1]


def screenshot_top_level_widgets():
    """Yield screenshots of all top-level widgets."""
    app = QApplication.instance()
    for screen_idx, screen in enumerate(app.screens(), 1):
        logger.debug("Screen %d: %s %s", screen_idx, screen, screen.geometry())

    primary_screen = app.primaryScreen()
    logger.debug("Primary screen: %s", primary_screen)

    def by_title(widget):
        return widget.windowTitle() or str(id(widget))

    index = 0
    for widget in sorted(app.topLevelWidgets(), key=by_title):
        if not widget.isVisible():
            continue
        screen = (
            widget.screen()
            if hasattr(widget, "screen")
            else primary_screen
        )
        screenshot = screen.grabWindow(widget.winId())
        name = widget.windowTitle().replace(" ", "_")
        suffix = f".{name}" if name else ""
        index += 1
        yield f"{index}{suffix}", screenshot


def save_all_screenshots(format="png") -> tuple[str, list[str]]:
    """Save screenshots of all top-level widgets to SCREENSHOT_DIR."""
    screenshots = []
    screenshot_id = str(uuid.uuid4())[:8]
    for name, screenshot in screenshot_top_level_widgets():
        fn = str(SCREENSHOT_DIR / f"{screenshot_id}.{name}.{format}")
        screenshot.save(fn, format)
        logger.info("Saved screenshot: %s", fn)
        screenshots.append(fn)
    return screenshot_id, screenshots


def log_exception_to_central_server(
    exc_info, *,
    context='exception',
    message=None,
    level=logging.ERROR,
    save_screenshots: bool = True,
    stacklevel=1,
):
    """
    Log an exception to the central server (i.e., logstash/grafana).

    Parameters
    ----------
    exc_info : (exc_type, exc_value, exc_traceback)
        The exception information.

    context : str, optional
        Additional context for the log message.

    message : str, optional
        Override the default log message.

    level : int, optional
        The log level to use.  Defaults to ERROR.

    save_screenshots : bool, optional
        Save screenshots of all top-level widgets and attach a screenshot ID to
        the log message.

    stacklevel : int, optional
        The stack level of the message being reported.  Defaults to 1,
        meaning that the message will be reported as having come from
        the caller of ``log_exception_to_central_server``.  Applies
        only to Python 3.8+, and ignored below.
    """
    exc_type, exc_value, exc_traceback = exc_info
    if issubclass(exc_type, NO_LOG_EXCEPTIONS):
        return

    if not pcdsutils.log.logger.handlers:
        # Do not allow log messages unless the central logger has been
        # configured with a log handler.  Otherwise, the log message will
        # hit the default handler and output to the terminal.
        return

    message = message or f'[{context}] {exc_value}'
    if save_screenshots:
        try:
            screenshot_id, screenshot_files = save_all_screenshots()
        except Exception:
            logger.exception("Failed to save screenshots")
        else:
            screenshots = "\n".join(
                f'screenshot{idx}="{screenshot_fn}"'
                for idx, screenshot_fn in enumerate(screenshot_files, 1)
            )
            message = (
                f'{message}\nscreenshot_id={screenshot_id}\n{screenshots}'
            )

    kwargs = dict()
    kwargs = dict(stacklevel=stacklevel + 1)

    pcdsutils.log.logger.log(level, message, exc_info=exc_info, **kwargs)


@functools.lru_cache(maxsize=1)
def get_fully_qualified_domain_name():
    """Get the fully qualified domain name of this host."""
    try:
        return socket.getfqdn()
    except Exception:
        logger.warning(
            "Unable to get machine name.  Things like centralized "
            "logging may not work."
        )
        logger.debug("getfqdn failed", exc_info=True)
        return ""


def centralized_logging_enabled() -> bool:
    """Returns True if centralized logging should be enabled."""
    fqdn = get_fully_qualified_domain_name()
    return any(fqdn.endswith(domain) for domain in LOG_DOMAINS)
