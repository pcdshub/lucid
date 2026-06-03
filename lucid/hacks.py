from epics.pv import PV
from ophyd.ophydobj import OphydObject
from ophyd.signal import EpicsSignalBase


def setup_rw_hack():
    OphydObject.add_instantiation_callback(ensure_read_write_on_conn)


def ensure_read_write_on_conn(instance):
    if not isinstance(instance, EpicsSignalBase):
        return
    instance.subscribe(update_rw, event_type=instance.SUB_META, run=False)


def update_rw(obj: EpicsSignalBase, connected: bool, **md):
    if connected and not obj.read_access:
        pv_objs: list[PV] = [obj._read_pv] # type: ignore
        try:
            pv_objs.append(obj._write_pv) # type: ignore
        except AttributeError:
            ...
        for pv in pv_objs:
            pv.force_read_access_rights()
            obj._pv_access_callback(read_access=pv.read_access, write_access=pv.write_access, pv=pv)
