import typing

from esg.supervisors.basereload import BaseReload
from esg.supervisors.multiprocess import Multiprocess

if typing.TYPE_CHECKING:
    ChangeReload: typing.Type[BaseReload]  # pragma: no cover
else:
    try:
        from esg.supervisors.watchgodreload import WatchGodReload as ChangeReload
    except ImportError:  # pragma: no cover
        from esg.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
