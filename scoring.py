def get_score(data, key):
    val = data.get("14_scores", {}).get(key, {})
    if isinstance(val, dict):
        raw = val.get("score", 5)
    else:
        raw = val
    try:
        return max(1.0, min(10.0, float(raw)))
    except (TypeError, ValueError):
        return 5.0

def calculate_final_score(data):
    return round((
        get_score(data, "dxw_fitment")           * 0.20 +
        get_score(data, "operational_complexity") * 0.15 +
        get_score(data, "data_architecture_risk") * 0.15 +
        get_score(data, "governance_gap")         * 0.15 +
        get_score(data, "tech_modernization_need")* 0.10 +
        get_score(data, "ai_maturity")            * 0.10 +
        get_score(data, "timing_urgency")         * 0.10 +
        get_score(data, "account_potential")       * 0.05
    ) * 10, 2)

def get_tier(data):
    tier = data.get("15_summary", {}).get("tier", "")
    if tier in ["Tier 1", "Tier 2", "Tier 3"]: return tier
    f = calculate_final_score(data)
    return "Tier 1" if f >= 75 else "Tier 2" if f >= 50 else "Tier 3"