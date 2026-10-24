"""Chill models on hourly air temperature (BUILD.md 4.2, 4.3).

Inputs are hourly temperatures in °C. Thresholds for chill hours and Utah are
FNRIC's, defined in °F, so we convert before comparing.

Dynamic Model (Fishman et al. 1987, constants as in chillR and xclim) runs in
numba and accepts/returns the model state (inter_e, xi) so a series can be
continued exactly. Never add CP totals from separate segments: continue the
state instead.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

E0 = 4153.5
E1 = 12888.8
A0 = 1.395e5
A1 = 2.567e18
SLOPE = 1.6
TF = 277.0

# Kelvin offset. FNRIC (like chillR) uses T + 273: their stemwater endpoint's
# dynmod_xi matches ours to 0.0 and dynmod_inter_e to 2e-16 with 273, but is
# off by 0.05 with 273.15 (checked on CIMIS-6, 300 hours, 2026-10-22).
# xclim converts with 273.15, so the xclim test feeds it the same Kelvin series.
TK_OFFSET = 273.0


@njit(cache=True)
def _dynamic(tc, inter_e0, xi0, tk_offset, start):
    n = tc.shape[0]
    portions = np.zeros(n)
    aa = A0 / A1
    ee = E1 - E0
    inter_e_prev = inter_e0
    xi_prev = xi0
    for i in range(start, n):
        t = tc[i]
        if math.isnan(t):
            # Missing hour: hold state, add nothing. Callers interpolate short gaps first.
            continue
        tk = t + tk_offset
        sr = math.exp(SLOPE * TF * (tk - TF) / tk)
        xi = sr / (1.0 + sr)
        xs = aa * math.exp(ee / tk)
        ak1 = A1 * math.exp(-E1 / tk)
        if inter_e_prev < 1.0:
            s = inter_e_prev
        else:
            s = inter_e_prev - inter_e_prev * xi_prev
        inter_e = xs - (xs - s) * math.exp(-ak1)
        if inter_e >= 1.0:
            portions[i] = inter_e * xi
        inter_e_prev = inter_e
        xi_prev = xi
    return portions, inter_e_prev, xi_prev


def dynamic_portions(tc, state=None, tk_offset: float = TK_OFFSET):
    """Hourly chill portions. Returns (portions per hour, final state (inter_e, xi)).

    state=None is a fresh season start: like xclim and chillR, the first hour's
    intermediate is 0 and the recursion starts at the second hour. Passing a
    state continues a series exactly, starting at its first hour.
    """
    arr = np.ascontiguousarray(tc, dtype=np.float64)
    if state is None:
        p, e, x = _dynamic(arr, 0.0, 0.0, float(tk_offset), 1)
    else:
        p, e, x = _dynamic(arr, float(state[0]), float(state[1]), float(tk_offset), 0)
    return p, (e, x)


@njit(cache=True)
def _dynamic_states(tc, inter_e0, xi0, tk_offset, start, every):
    """Portions per hour plus the state after every `every`-th hour (e.g. 24 = day ends)."""
    n = tc.shape[0]
    portions = np.zeros(n)
    m = n // every
    states = np.zeros((m, 2))
    aa = A0 / A1
    ee = E1 - E0
    inter_e_prev = inter_e0
    xi_prev = xi0
    for i in range(n):
        t = tc[i]
        if i >= start and not math.isnan(t):
            tk = t + tk_offset
            sr = math.exp(SLOPE * TF * (tk - TF) / tk)
            xi = sr / (1.0 + sr)
            xs = aa * math.exp(ee / tk)
            ak1 = A1 * math.exp(-E1 / tk)
            if inter_e_prev < 1.0:
                s = inter_e_prev
            else:
                s = inter_e_prev - inter_e_prev * xi_prev
            inter_e = xs - (xs - s) * math.exp(-ak1)
            if inter_e >= 1.0:
                portions[i] = inter_e * xi
            inter_e_prev = inter_e
            xi_prev = xi
        if (i + 1) % every == 0 and (i + 1) // every - 1 < m:
            states[(i + 1) // every - 1, 0] = inter_e_prev
            states[(i + 1) // every - 1, 1] = xi_prev
    return portions, states


def dynamic_with_day_states(tc, state=None, tk_offset: float = TK_OFFSET):
    """Hourly portions and the model state at the end of each 24-hour block."""
    arr = np.ascontiguousarray(tc, dtype=np.float64)
    if state is None:
        return _dynamic_states(arr, 0.0, 0.0, float(tk_offset), 1, 24)
    return _dynamic_states(arr, float(state[0]), float(state[1]), float(tk_offset), 0, 24)


@njit(cache=True)
def _dynamic_batch_end(tc2d, inter_e0, xi0, tk_offset):
    """Continue many series (rows) from one shared state; return cumulative CP per row per hour."""
    m, n = tc2d.shape
    out = np.zeros((m, n))
    for r in range(m):
        p, _, _ = _dynamic(tc2d[r], inter_e0, xi0, tk_offset, 0)
        acc = 0.0
        for i in range(n):
            acc += p[i]
            out[r, i] = acc
    return out


def dynamic_batch_cumulative(tc2d, state=(0.0, 0.0), tk_offset: float = TK_OFFSET):
    arr = np.ascontiguousarray(tc2d, dtype=np.float64)
    return _dynamic_batch_end(arr, float(state[0]), float(state[1]), float(tk_offset))


def c_to_f(tc):
    # Rounded so readings that were exact °F values (e.g. 36.0) do not drift across a threshold.
    return np.round(np.asarray(tc, dtype=np.float64) * 9.0 / 5.0 + 32.0, 6)


def hours_below_45(tc):
    tf = c_to_f(tc)
    return np.where(np.isnan(tf), 0.0, (tf <= 45.0).astype(np.float64))


def hours_32_45(tc):
    tf = c_to_f(tc)
    return np.where(np.isnan(tf), 0.0, ((tf > 32.0) & (tf <= 45.0)).astype(np.float64))


def utah_units(tc):
    tf = c_to_f(tc)
    u = np.select(
        [tf <= 34, tf <= 36, tf <= 48, tf <= 54, tf <= 60, tf <= 65],
        [0.0, 0.5, 1.0, 0.5, 0.0, -0.5],
        default=-1.0,
    )
    return np.where(np.isnan(tf), 0.0, u)
