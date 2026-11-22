"""The timeouts in front of a solver must nest: each outer layer waits longer."""

import runpy
from pathlib import Path

from quantumsolver.routes import SOLVER_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parent.parent


def test_gunicorn_outlasts_the_solver_timeout():
    # gunicorn kills a worker at its own timeout; if that came first, the client would get
    # a dropped connection instead of {"answer": "timeout"}.
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    assert config["timeout"] > SOLVER_TIMEOUT_SECONDS


def test_idle_sync_worker_still_outlasts_the_solver_timeout():
    # An idle sync worker reports in, then waits up to timeout / 2 for a connection; the
    # arbiter counts from that report. A request arriving at the end of the wait therefore
    # gets only timeout / 2 before the worker is killed, which must still exceed the solver.
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    assert config["timeout"] / 2 > SOLVER_TIMEOUT_SECONDS


def test_sample_nginx_config_outlasts_gunicorn():
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    nginx = (ROOT / "deploy" / "quantumsolver.nginx").read_text()
    line = next(x for x in nginx.splitlines() if "proxy_read_timeout" in x)
    seconds = int(line.split()[1].rstrip("s;"))
    assert seconds > config["timeout"]
