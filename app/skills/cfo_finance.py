"""
CFO Finance Skill Module
=========================
Tools for the Chief Financial Officer. Budget tracking,
ROI analysis, and financial reporting.
"""
import json
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _SCRIPT_DIR.parent.parent

if "Personal assistant" in str(_SERVER_ROOT):
    _DATA_DIR = _SERVER_ROOT / "data"
else:
    _DATA_DIR = Path("/tmp/data")

BUDGET_FILE = _DATA_DIR / "budget_ledger.json"


def budget_entry(category: str, amount: float, entry_type: str = "opex", description: str = "", currency: str = "BGN") -> dict:
    """
    Logs a financial entry (expense or income) to the SmartDome budget ledger.
    
    Args:
        category: Expense category (e.g., 'Materials', 'SaaS', 'Travel', 'R&D', 'Legal').
        amount: Amount in the specified currency. Positive for expense, negative for income.
        entry_type: 'opex' for Operating Expenses, 'capex' for Capital Expenditures, 'income' for Revenue.
        description: Details about this financial entry.
        currency: Currency code. Default 'BGN'.
    
    Returns:
        dict: Confirmation with entry ID and updated budget summary.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        data = {"entries": [], "summary": {"total_opex": 0, "total_capex": 0, "total_income": 0}}
        if BUDGET_FILE.exists():
            with open(BUDGET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        entry = {
            "id": f"fin_{int(datetime.now().timestamp())}",
            "category": category,
            "amount": amount,
            "type": entry_type.lower(),
            "description": description,
            "currency": currency,
            "logged_by": "CFO",
            "created_at": datetime.now().isoformat(),
            "status": "recorded"
        }
        data["entries"].insert(0, entry)
        
        # Recalculate summary
        data["summary"]["total_opex"] = sum(e["amount"] for e in data["entries"] if e["type"] == "opex")
        data["summary"]["total_capex"] = sum(e["amount"] for e in data["entries"] if e["type"] == "capex")
        data["summary"]["total_income"] = sum(abs(e["amount"]) for e in data["entries"] if e["type"] == "income")
        
        with open(BUDGET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"Budget entry logged: {category} - {amount} {currency} ({entry_type})",
            "id": entry["id"],
            "running_total": {
                "opex": data["summary"]["total_opex"],
                "capex": data["summary"]["total_capex"],
                "income": data["summary"]["total_income"]
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_budget_summary(period: str = "all") -> dict:
    """
    Returns the current budget summary including burn rate and categories.
    
    Args:
        period: Time period to summarize - 'all', 'month', or 'week'.
    
    Returns:
        dict: Budget breakdown with totals per category and burn rate.
    """
    try:
        if not BUDGET_FILE.exists():
            return {"success": True, "message": "No budget entries yet.", "entries": [], "totals": {}}
        
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        entries = data.get("entries", [])
        
        # Filter by period if needed
        if period == "month":
            cutoff = datetime.now().replace(day=1).isoformat()
            entries = [e for e in entries if e.get("created_at", "") >= cutoff]
        elif period == "week":
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            entries = [e for e in entries if e.get("created_at", "") >= cutoff]
        
        # Group by category
        by_category = {}
        for e in entries:
            cat = e.get("category", "Uncategorized")
            by_category[cat] = by_category.get(cat, 0) + e.get("amount", 0)
        
        total_expenses = sum(e["amount"] for e in entries if e["type"] in ["opex", "capex"])
        total_income = sum(abs(e["amount"]) for e in entries if e["type"] == "income")
        
        return {
            "success": True,
            "period": period,
            "total_expenses": total_expenses,
            "total_income": total_income,
            "net": total_income - total_expenses,
            "by_category": by_category,
            "entry_count": len(entries),
            "recent_entries": entries[:5]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def roi_calculator(investment: float, expected_return: float, timeframe_months: int = 12) -> dict:
    """
    Calculates Return on Investment (ROI) metrics for a proposed expenditure.
    
    Args:
        investment: Total investment amount in BGN.
        expected_return: Expected total return in BGN over the timeframe.
        timeframe_months: Timeframe in months for the return. Default 12.
    
    Returns:
        dict: ROI percentage, monthly return rate, payback period, and recommendation.
    """
    if investment <= 0:
        return {"success": False, "error": "Investment must be positive."}
    
    roi_pct = ((expected_return - investment) / investment) * 100
    monthly_return = (expected_return - investment) / timeframe_months if timeframe_months > 0 else 0
    payback_months = investment / (expected_return / timeframe_months) if expected_return > 0 else float('inf')
    
    # Recommendation logic
    if roi_pct >= 100:
        recommendation = "STRONG APPROVE — High ROI, proceed immediately."
    elif roi_pct >= 30:
        recommendation = "APPROVE — Acceptable ROI for the timeframe."
    elif roi_pct >= 10:
        recommendation = "CONDITIONAL — Marginal ROI. Negotiate better terms."
    elif roi_pct >= 0:
        recommendation = "HOLD — Near break-even. Review alternatives."
    else:
        recommendation = "REJECT — Negative ROI. Not recommended."
    
    return {
        "success": True,
        "investment": investment,
        "expected_return": expected_return,
        "timeframe_months": timeframe_months,
        "roi_percentage": round(roi_pct, 2),
        "monthly_return": round(monthly_return, 2),
        "payback_months": round(payback_months, 1),
        "recommendation": recommendation
    }
