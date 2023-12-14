"""
Shim module for dealing with the repeatedly changing import API for
the conda builds of PyQtAds.

The pypi builds do not seem to have the same issue.
"""
try:
    # pre-v4.0.0
    from PyQtAds import QtAds as ads
except ImportError:
    try:
        # from v4.0.0 to v4.1.1
        from PyQtAds import ads
    except ImportError:
        # starting at v4.2.0 (latest, for now)
        import PyQtAds as ads

if not hasattr(ads, "CDockWidget"):
    import PyQtAds
    raise ImportError(f"Submodule name for PyQtAds changed (again): {dir(PyQtAds)}")
