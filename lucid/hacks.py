from epics.pv import PV
from ophyd.ophydobj import OphydObject
from ophyd.signal import EpicsSignalBase


def setup_rw_hack():
    """
    Sets up a callback on every epics signal to double-check access permissions on reconnect.

    There is an issue on las-console that appears often (every 4ish hours on average) when
    running lucid where all of the PVs "disconnect" and then "reconnect" but don't get an
    access rights update on reconnect, so the ophyd signals get stuck without
    read and right access for the rest of the runtime of the program.
    """
    OphydObject.add_instantiation_callback(ensure_read_write_on_conn)


def ensure_read_write_on_conn(instance):
    """
    Subscripe our update function if and only if it is an EPICS signal
    """
    if not isinstance(instance, EpicsSignalBase):
        return
    instance.subscribe(update_rw, event_type=instance.SUB_META, run=False)


def update_rw(obj: EpicsSignalBase, connected: bool, **md):
    """
    If the signal appears to be affected by the bug, reach into pyepics and get the access rights update.
    """
    if connected and not obj.read_access:
        pv_objs: list[PV] = [obj._read_pv] # type: ignore
        try:
            pv_objs.append(obj._write_pv) # type: ignore
        except AttributeError:
            ...
        for pv in pv_objs:
            pv.force_read_access_rights()
            obj._pv_access_callback(read_access=pv.read_access, write_access=pv.write_access, pv=pv)
