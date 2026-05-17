"""
Mock tools for the AI engineer assignment.

You may import these from your agent. Do not modify the data or function signatures.

To simulate the passage of time between Session 1 (Monday) and Session 2 (Thursday),
flip CURRENT_SESSION from 1 to 2 before running Session 2.
"""

# Session 1 = Monday, Nov 3, 2025 (salary just credited that morning)
# Session 2 = Thursday, Nov 6, 2025 (rent has been paid, a few more food orders)
CURRENT_SESSION = 1  # flip to 2 before running session 2


def get_recent_transactions(days: int) -> list[dict]:
    """
    Transactions from the last N days, relative to 'today' for the current session.
    Negative amount = debit (money out). Positive = credit (money in). INR.
    Filtering by `days` is left to the caller.
    """
    txns = [
        {"date": "2025-10-01", "amount": -25000, "category": "rent",          "merchant": "Landlord"},
        {"date": "2025-10-03", "amount": -1200,  "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-10-04", "amount": -1800,  "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-10-07", "amount": -4500,  "category": "shopping",      "merchant": "Myntra"},
        {"date": "2025-10-08", "amount": -1100,  "category": "food_delivery", "merchant": "Zomato"},
        {"date": "2025-10-10", "amount": -10000, "category": "investment",    "merchant": "MF SIP"},
        {"date": "2025-10-11", "amount": -950,   "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-10-13", "amount": -3200,  "category": "groceries",     "merchant": "BigBasket"},
        {"date": "2025-10-15", "amount": -1500,  "category": "entertainment", "merchant": "BookMyShow"},
        {"date": "2025-10-17", "amount": -2200,  "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-10-20", "amount": -890,   "category": "food_delivery", "merchant": "Zomato"},
        {"date": "2025-10-22", "amount": -2200,  "category": "fuel",          "merchant": "IOCL"},
        {"date": "2025-10-24", "amount": -1500,  "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-10-27", "amount": -1200,  "category": "food_delivery", "merchant": "Zomato"},
        {"date": "2025-10-28", "amount": -3500,  "category": "shopping",      "merchant": "Amazon"},
        {"date": "2025-10-30", "amount": -1400,  "category": "food_delivery", "merchant": "Swiggy"},
        {"date": "2025-11-01", "amount": 120000, "category": "salary",        "merchant": "Employer"},
        {"date": "2025-11-02", "amount": -650,   "category": "food_delivery", "merchant": "Swiggy"},
    ]
    if CURRENT_SESSION == 2:
        txns += [
            {"date": "2025-11-03", "amount": -1100,  "category": "food_delivery", "merchant": "Zomato"},
            {"date": "2025-11-04", "amount": -780,   "category": "food_delivery", "merchant": "Swiggy"},
            {"date": "2025-11-05", "amount": -25000, "category": "rent",          "merchant": "Landlord"},
            {"date": "2025-11-06", "amount": -1300,  "category": "food_delivery", "merchant": "Swiggy"},
        ]
    return txns


def get_account_balance() -> dict:
    """Current balances across the user's accounts (INR)."""
    if CURRENT_SESSION == 1:
        return {
            "checking":      128000,
            "savings":       145000,
            "house_fund":     95000,
            "mutual_funds":  280000,
        }
    else:
        # Thursday — rent has been paid, plus a few food orders
        return {
            "checking":       99820,
            "savings":       145000,
            "house_fund":     95000,
            "mutual_funds":  280000,
        }


def get_upcoming_bills(days: int = 30) -> list[dict]:
    """Scheduled bills/payments due in the next N days from 'today' for the current session."""
    if CURRENT_SESSION == 1:
        return [
            {"date": "2025-11-05", "amount": 25000, "description": "Rent (auto-debit)"},
            {"date": "2025-11-10", "amount": 10000, "description": "SIP - Mutual Funds"},
            {"date": "2025-11-15", "amount": 3500,  "description": "Internet + Mobile"},
            {"date": "2025-11-20", "amount": 8000,  "description": "Credit Card (auto-debit)"},
        ]
    else:
        # Rent has been paid; the rest remain
        return [
            {"date": "2025-11-10", "amount": 10000, "description": "SIP - Mutual Funds"},
            {"date": "2025-11-15", "amount": 3500,  "description": "Internet + Mobile"},
            {"date": "2025-11-20", "amount": 8000,  "description": "Credit Card (auto-debit)"},
        ]


def set_reminder(date: str, content: str) -> dict:
    """
    Log a reminder. `date` is 'YYYY-MM-DD'.
    Returns a confirmation dict with a reminder_id.
    """
    return {
        "status": "set",
        "reminder_id": f"rem_{abs(hash(content)) % 10000}",
        "date": date,
        "content": content,
    }


# Convenience: a tool registry you may use or ignore.
TOOLS = {
    "get_recent_transactions": get_recent_transactions,
    "get_account_balance":     get_account_balance,
    "get_upcoming_bills":      get_upcoming_bills,
    "set_reminder":            set_reminder,
}
