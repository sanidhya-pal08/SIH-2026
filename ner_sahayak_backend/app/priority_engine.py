import math

def calculate_priority(urgency: str, category: str, population: int, isolation: float, stockout_days: int, local_supply: int = 0):
    """
    Score = w_u * U + w_c * C + w_p * log10(P) + w_i * I + w_s * S - w_l * L
    """
    # Weights
    w_u = 1.0
    w_c = 1.0
    w_p = 2.0  # Slightly boost population impact
    w_i = 15.0 # Isolation is 0.0 to 1.0, give it up to 15 points
    w_s = 1.0
    w_l = 1.0

    # U: Urgency mapping
    u_map = {"routine": 10, "urgent": 30, "emergency": 60}
    u_val = u_map.get(urgency.lower(), 10)

    # C: Category mapping
    c_map = {
        "Medical/Blood/O2": 30,
        "Drinking Water": 25,
        "Food": 15,
        "General": 5
    }
    c_val = c_map.get(category, 5)

    # P: Population component
    p_val = math.log10(population) if population and population > 0 else 0

    # I: Isolation component
    i_val = isolation if isolation else 0.0

    # S: Stockout Risk (0 to 20 based on remaining days of supply)
    s_val = max(0, 20 - stockout_days)

    # L: Local Supply
    l_val = local_supply

    raw_score = (w_u * u_val) + (w_c * c_val) + (w_p * p_val) + (w_i * i_val) + (w_s * s_val) - (w_l * l_val)
    
    # Normalize or cap between 0 and 100
    final_score = max(0.0, min(100.0, float(raw_score)))

    breakdown = {
        "urgency_score": round(u_val * w_u, 2),
        "criticality_score": round(c_val * w_c, 2),
        "population_score": round(p_val * w_p, 2),
        "isolation_score": round(i_val * w_i, 2),
        "stockout_score": round(s_val * w_s, 2),
        "local_supply_penalty": round(l_val * w_l, 2),
        "raw_total": round(raw_score, 2),
        "final_capped": round(final_score, 2)
    }

    return round(final_score, 2), breakdown
