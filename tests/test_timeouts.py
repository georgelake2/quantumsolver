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


def test_sample_nginx_config_outlasts_gunicorn():
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    nginx = (ROOT / "deploy" / "quantumsolver.nginx").read_text()
    line = next(x for x in nginx.splitlines() if "proxy_read_timeout" in x)
    seconds = int(line.split()[1].rstrip("s;"))
    assert seconds > config["timeout"]
