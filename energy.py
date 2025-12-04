#!/usr/bin/env python3
import threading
from time import sleep
import random
import logging
from . import config
from . import state

logger = logging.getLogger(__name__)


def _compute_inr_cost(kwh: float) -> float:
    """Compute INR cost using a simple slabed tariff.

        Use a Tamil Nadu bi-monthly billing-inspired slab for demo purposes.

        Provided official ranges (example excerpts):
            - 1–100 units => ₹0.00/unit (free)
            - 101–200 units => ~₹2.35/unit
            - 801–1000 units => ₹10.50/unit

        The demo needs a complete set of slabs. For unspecified ranges I pick conservative
        mid-range rates so the progression is smooth. These are demo assumptions and can be
        adjusted to match an exact tariff table.
    """
    remaining = kwh
    cost = 0.0
    # Tamil Nadu (bi-monthly) inspired slabs (units -> INR per unit)
    # 0-100: free, 101-200: 2.35, 201-800: 6.5 (assumed), 801-1000: 10.5, >1000: 12.0 (assumed)
    slabs = [
        (100, 0.0),
        (100, 2.35),
        (600, 6.5),
        (200, 10.5),
        (float('inf'), 12.0),
    ]
    for units, rate in slabs:
        if remaining <= 0:
            break
        take = min(remaining, units)
        cost += take * rate
        remaining -= take
    return round(cost, 2)


def simulate_energy_data():
    # Use config module so we always see up-to-date people_count
    while True:
        pc = state.get_people_count()
        if pc == 0:
            # reset usage and cost when empty for demo
            state.update_energy_data({
                "current_usage": 0.0,
                "total_consumption": 0.0,
                "cost_usd": 0.0,
                "cost_inr": 0.0,
                "cost": 0.0
            })
            logger.debug("simulate_energy_data: room empty, reset usage and cost")
        else:
            # current usage scales with people and has small random noise
            base = pc * 0.2
            var = random.uniform(-0.02, 0.02)
            current = max(0.0, round(base + var, 2))
            # integrate into total consumption (kWh) assuming current is kW sampled every second
            ed = state.get_energy_data()
            total = float(ed.get("total_consumption", 0.0)) + (current / 3600.0)
            total = round(total, 3)
            # compute costs: USD kept for historical reasons, INR is primary cost shown
            usd_rate_per_kwh = 0.12  # $ per kWh (demo)
            cost_usd = round(total * usd_rate_per_kwh, 2)
            cost_inr = _compute_inr_cost(total)
            # Use INR as the primary `cost` value so the dashboard shows INR by default
            state.update_energy_data({
                "current_usage": current,
                "total_consumption": total,
                "cost_usd": cost_usd,
                "cost_inr": cost_inr,
                "cost": cost_inr
            })
            logger.debug("simulate_energy_data: pc=%s current=%s total=%s cost=%s", pc, current, total, cost_usd)
        sleep(1)


def start_energy_thread():
    threading.Thread(target=simulate_energy_data, daemon=True).start()
    logger.info("Energy simulation thread started")