"""Tests for Shor's algorithm with every attempt recorded (/shors-traced)."""

import random

import pytest

from quantumsolver import shors_traced
from quantumsolver.app import app as flask_app


@pytest.fixture
def client():
    """Flask test client fixture."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def fixed_measurements(*outcomes):
    """A stand-in for the circuit: returns the given x values in order."""
    queue = list(outcomes)

    def measure(a, n):
        bits = n.bit_length()
        return queue.pop(0), 2 * bits, [pow(a, 1 << j, n) for j in range(2 * bits)]

    return measure


class FixedBases(random.Random):
    """An rng whose shuffle puts the given bases first."""

    def __init__(self, *first):
        super().__init__(0)
        self.first = list(first)

    def shuffle(self, x):
        rest = [b for b in x if b not in self.first]
        x[:] = self.first + rest


# --- decode: the classical steps after one measurement ---------------------------------


def test_convergents_of_a_simple_fraction():
    assert shors_traced.convergents(3, 8) == [(0, 1), (1, 2), (1, 3), (3, 8)]


def test_decode_x_zero_says_nothing():
    step = shors_traced.decode(0, 7, 15, 8)
    assert step["outcome"] == shors_traced.X_ZERO
    assert step["r"] is None


def test_decode_finds_period_and_factors():
    # N = 15, a = 7 has period 4; x = 64 is 1/4 of 256.
    step = shors_traced.decode(64, 7, 15, 8)
    assert step["outcome"] == shors_traced.FACTORED
    assert step["r"] == 4
    assert step["h"] == 4  # 7^2 mod 15
    assert step["factors"] == [3, 5]
    assert step["tested"] == [[4, 1]]


def test_decode_tries_multiples_when_the_fraction_is_reduced():
    # N = 15, a = 7: x = 128 is 1/2, which hides r = 4; 2 fails, 4 works.
    step = shors_traced.decode(128, 7, 15, 8)
    assert step["tested"] == [[2, 4], [4, 1]]
    assert step["r"] == 4


def test_decode_odd_period_starts_over():
    # N = 21, a = 4 has period 3; x = 1365 is close to 1/3 of 4096.
    step = shors_traced.decode(1365, 4, 21, 12)
    assert step["r"] == 3
    assert step["outcome"] == shors_traced.ODD_PERIOD


def test_decode_minus_one_starts_over():
    # N = 15, a = 14: 14^1 = 14 = -1, period 2, h = 14 = N - 1.
    step = shors_traced.decode(128, 14, 15, 8)
    assert step["r"] == 2
    assert step["h"] == 14
    assert step["outcome"] == shors_traced.MINUS_ONE


def test_decode_between_peaks_finds_no_period():
    # N = 15, a = 7: x = 23 is between peaks; its only candidate, 11, fails.
    step = shors_traced.decode(23, 7, 15, 8)
    assert step["outcome"] == shors_traced.NO_PERIOD
    assert step["tested"]


# --- trace: the whole run ---------------------------------------------------------------


def test_lucky_base_needs_no_circuit():
    record = shors_traced.trace(15, rng=FixedBases(6), measure=fixed_measurements())
    assert record["answer"] == [3, 5]
    assert record["attempts"] == [
        {"a": 6, "gcd": 3, "circuit": False, "outcome": "lucky", "factors": [3, 5]}
    ]


def test_failed_attempts_are_recorded_before_the_one_that_works():
    record = shors_traced.trace(
        15, rng=FixedBases(7, 2), measure=fixed_measurements(0, 64)
    )
    first, second = record["attempts"]
    assert first["a"] == 7 and first["outcome"] == "x_zero" and first["x"] == 0
    assert second["a"] == 2 and second["outcome"] == "factored" and second["x"] == 64
    assert second["multipliers"] == [2, 4, 1, 1, 1, 1, 1, 1]
    assert record["answer"] == [3, 5]
    assert record["counting_qubits"] == 8 and record["work_qubits"] == 4


def test_even_and_prime_power_are_split_classically():
    assert shors_traced.trace(22)["classical"] == "even"
    record = shors_traced.trace(49)
    assert record["classical"] == "perfect_power"
    assert record["answer"] == [7, 7]
    assert record["attempts"] == []


@pytest.mark.parametrize("n,expected", [(15, [3, 5]), (21, [3, 7]), (35, [5, 7])])
def test_real_simulator_run_factors(n, expected):
    """The real circuit on the simulator, end to end."""
    record = shors_traced.solve(n)
    assert record["answer"] == expected
    last = record["attempts"][-1]
    assert last["outcome"] in ("lucky", "factored")
    for attempt in record["attempts"][:-1]:
        assert attempt["outcome"] not in ("lucky", "factored")


# --- solve: input checks ----------------------------------------------------------------


@pytest.mark.parametrize(
    "data,message",
    [("15", "integer"), (True, "integer"), (3, "at least 4"), (1024, "too large")],
)
def test_solve_rejects_bad_input(data, message):
    assert message in shors_traced.solve(data)["answer"]


def test_solve_prime_has_no_attempts():
    record = shors_traced.solve({"N": 29})
    assert record["answer"] == [29]
    assert record["classical"] == "prime"


def test_endpoint(client):
    response = client.post("/shors-traced", json={"N": 15})
    body = response.get_json()
    assert body["answer"] == [3, 5]
    assert body["attempts"]
