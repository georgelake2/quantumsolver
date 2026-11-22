"""Gunicorn configuration for quantumsolver."""

import multiprocessing

# Each request blocks for up to 60 s (internal timeout), so sync workers are correct.
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Half of this must exceed the 60-second in-app timeout (SOLVER_TIMEOUT_SECONDS in
# routes.py). An idle sync worker last reports in before waiting up to timeout / 2 for a
# connection, and the arbiter kills a worker `timeout` seconds after its last report, so a
# request that arrives late in that wait gets only about timeout / 2. 130 leaves 65 s.
timeout = 130

bind = [
    "unix:/run/quantumsolver/gunicorn.sock",
    "[::]:27100",
]

# Log to stdout/stderr so systemd journal captures everything.
accesslog = "-"
errorlog = "-"
loglevel = "info"
