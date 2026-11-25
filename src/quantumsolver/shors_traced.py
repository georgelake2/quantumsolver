"""
Shor's algorithm with every attempt recorded, for Redux's step-by-step visualizations.
George Lake - November 2026

shors_quantum.solve answers only with the factors. This module runs the same algorithm and
also returns what happened along the way, so Redux can show the student the whole run:

1. Pick a random base a (2 <= a <= N - 2) and compute gcd(a, N). If it is more than 1,
   a already shares a factor with N and no circuit is needed.
2. Otherwise run the order-finding circuit once on the simulator and measure x.
3. Decode x classically: the continued fractions of x / 2^t give candidate periods k
   (bottom number below N), and the first k, or multiple of k below N, with
   a^k mod N = 1 is the period r.
4. If r is even and h = a^(r/2) mod N is not N - 1, gcd(h - 1, N) and gcd(h + 1, N) are
   the two factors. Otherwise start over with a new base.

The circuit is shors_quantum.ShorCircuit, so the quantum part is identical to the
/prime-factorization-quantum endpoint. Unlike that endpoint, this one splits N once and
does not recurse: it is meant for an RSA modulus, a product of two primes.
"""

import math
import random

from qiskit_aer import AerSimulator

from quantumsolver.shors_quantum import ShorCircuit

# The same limit as /prime-factorization-quantum: N below 10 bits.
MAX_BITS = 10
# How many bases to try before giving up. Each attempt fails with probability well below
# one half for the N this serves, so reaching the limit means something is wrong.
MAX_ATTEMPTS = 20

# Why an attempt ended. "lucky" and "factored" succeed; the rest start over.
LUCKY = "lucky"
FACTORED = "factored"
X_ZERO = "x_zero"
NO_PERIOD = "no_period"
ODD_PERIOD = "odd_period"
MINUS_ONE = "minus_one"


def convergents(numerator: int, denominator: int) -> list[tuple[int, int]]:
    """Continued-fraction convergents h/k of numerator/denominator, in order."""
    result = []
    h_prev, h = 0, 1
    k_prev, k = 1, 0
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        h_prev, h = h, quotient * h + h_prev
        k_prev, k = k, quotient * k + k_prev
        result.append((h, k))
        numerator, denominator = denominator, remainder
    return result


def decode(x: int, a: int, n: int, counting_bits: int) -> dict:
    """Turn one measurement x into a period and, if possible, the factors of n.

    Returns the classical steps as data: the convergents shown to the student, the
    candidate periods tested with a^k mod n, and the outcome.
    """
    size = 1 << counting_bits
    step = {"x": x, "convergents": [], "tested": [], "r": None, "h": None}
    if x == 0:
        return step | {"outcome": X_ZERO}

    common = math.gcd(x, size)
    fractions = [[h, k] for h, k in convergents(x // common, size // common) if k < n]
    step["convergents"] = fractions
    # Skip the trivial ones (0/1, and whole numbers) and try the closest fraction first.
    candidates = [k for h, k in reversed(fractions) if h > 0 and k > 1]

    tried = []
    r = None
    for k in candidates:
        multiple = k
        while multiple < n and r is None:
            if multiple not in tried:
                tried.append(multiple)
                if pow(a, multiple, n) == 1:
                    r = multiple
            multiple += k
        if r is not None:
            break
    step["tested"] = [[c, pow(a, c, n)] for c in tried]
    if r is None:
        return step | {"outcome": NO_PERIOD}

    step["r"] = r
    if r % 2:
        return step | {"outcome": ODD_PERIOD}
    h = pow(a, r // 2, n)
    step["h"] = h
    if h == n - 1:
        return step | {"outcome": MINUS_ONE}
    p, q = sorted((math.gcd(h - 1, n), math.gcd(h + 1, n)))
    return step | {
        "outcome": FACTORED,
        "gcd_minus": math.gcd(h - 1, n),
        "gcd_plus": math.gcd(h + 1, n),
        "factors": [p, q],
    }


def perfect_power_root(n: int) -> int | None:
    """The base b if n = b^k for some k >= 2, else None. Shor's period finding needs n
    to have two different prime factors, so a prime power is split classically."""
    for exponent in range(n.bit_length(), 1, -1):
        root = round(n ** (1 / exponent))
        for candidate in (root - 1, root, root + 1):
            if candidate > 1 and candidate**exponent == n:
                return candidate
    return None


def measure_once(a: int, n: int, simulator) -> tuple[int, int, list[int]]:
    """Run the order-finding circuit once and return (x, counting qubits, multipliers)."""
    circuit = ShorCircuit(a, n)
    result = circuit.run_simulation(simulator)
    x = int(result.get_memory()[0], 2)
    multipliers = [pow(a, 1 << j, n) for j in range(circuit.n_count)]
    return x, circuit.n_count, multipliers


def trace(
    n: int, rng: random.Random | None = None, simulator=None, measure=None
) -> dict:
    """Split n with Shor's algorithm, recording every attempt.

    `measure(a, n)` runs the circuit once and returns (x, counting qubits, multipliers);
    tests pass their own to make a run predictable.
    """
    rng = rng or random.Random()
    if measure is None:
        sim = simulator or AerSimulator()

        def measure(base, modulus):
            return measure_once(base, modulus, sim)

    work_bits = n.bit_length()
    record = {
        "n": n,
        "counting_qubits": 2 * work_bits,
        "work_qubits": work_bits,
        "attempts": [],
        "classical": None,
    }

    if n % 2 == 0:
        record["classical"] = "even"
        record["answer"] = [2, n // 2]
        return record

    root = perfect_power_root(n)
    if root is not None:
        record["classical"] = "perfect_power"
        record["answer"] = [root, n // root]
        return record

    bases = list(range(2, n - 1))
    rng.shuffle(bases)
    for a in bases[:MAX_ATTEMPTS]:
        common = math.gcd(a, n)
        attempt = {"a": a, "gcd": common, "circuit": common == 1}
        record["attempts"].append(attempt)
        if common > 1:
            p, q = sorted((common, n // common))
            attempt |= {"outcome": LUCKY, "factors": [p, q]}
            record["answer"] = [p, q]
            return record

        x, counting_bits, multipliers = measure(a, n)
        attempt["multipliers"] = multipliers
        attempt |= decode(x, a, n, counting_bits)
        if attempt["outcome"] == FACTORED:
            record["answer"] = attempt["factors"]
            return record

    record["answer"] = f"no factor found after {len(record['attempts'])} bases"
    return record


def solve(data) -> dict:
    """Endpoint entry point. Takes N, or {"N": N}; returns the record (see trace)."""
    n = data["N"] if isinstance(data, dict) else data
    if not isinstance(n, int) or isinstance(n, bool):
        return {"answer": "Input must be an integer"}
    if n < 4:
        return {"answer": "Input must be at least 4"}
    if n.bit_length() >= MAX_BITS:
        return {"answer": f"Input too large (limit < {MAX_BITS} bits)"}
    if all(n % d for d in range(2, math.isqrt(n) + 1)):
        return {"answer": [n], "n": n, "attempts": [], "classical": "prime"}
    return trace(n)
