
CURRENCY_SYMBOLS = {
    "EUR": ["€", 1.0],
    "USD": ["$", 1.091],
    "GBP": ["£", 0.8367],
    "ARGs": ["$", 1724.0],
}
default_Currency = "EUR"
TERM_DAYS = {"Immediate": 0, "15 Days": 15, "30 Days": 30, "45 Days": 45}


def money(amount: float, currency: str) -> str:
    symbol, factor = CURRENCY_SYMBOLS.get(currency, currency)
    prefix = "-" if amount < 0 else ""
    return f"{prefix}{symbol} {abs(amount*factor):,.2f}"

