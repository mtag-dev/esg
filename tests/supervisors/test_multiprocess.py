import signal

from esg import Config
from esg.supervisors import Multiprocess


def run(sockets):
    pass  # pragma: no cover


def test_multiprocess_run():
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.signal_handler(sig=signal.SIGINT, frame=None)
    supervisor.run()
