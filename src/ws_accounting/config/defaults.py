"""Default chart of accounts, categories, and commodity settings."""

# Top-level account types
ACCOUNT_TYPES = ["assets", "liabilities", "income", "expenses", "equity"]

# Default expense categories for budgeting
DEFAULT_CATEGORIES: list[str] = [
    "expenses:food:groceries",
    "expenses:food:dining",
    "expenses:food:coffee",
    "expenses:housing:rent",
    "expenses:housing:utilities",
    "expenses:housing:internet",
    "expenses:transport:gas",
    "expenses:transport:parking",
    "expenses:transport:public transit",
    "expenses:health:insurance",
    "expenses:health:medical",
    "expenses:health:pharmacy",
    "expenses:entertainment:subscriptions",
    "expenses:entertainment:movies",
    "expenses:shopping:clothing",
    "expenses:shopping:electronics",
    "expenses:shopping:household",
    "expenses:personal:gym",
    "expenses:personal:haircut",
    "expenses:education",
    "expenses:insurance",
    "expenses:taxes",
    "expenses:gifts",
    "expenses:charity",
    "expenses:other",
]

DEFAULT_INCOME_CATEGORIES: list[str] = [
    "income:salary",
    "income:freelance",
    "income:interest",
    "income:other",
]

DEFAULT_ASSET_ACCOUNTS: list[str] = [
    "assets:checking",
    "assets:savings",
    "assets:cash",
]

DEFAULT_LIABILITY_ACCOUNTS: list[str] = [
    "liabilities:credit card",
]

# Default accounts for new journals
DEFAULT_ACCOUNTS: list[str] = (
    DEFAULT_ASSET_ACCOUNTS
    + DEFAULT_LIABILITY_ACCOUNTS
    + DEFAULT_INCOME_CATEGORIES
    + DEFAULT_CATEGORIES
    + ["equity:opening balances"]
)

# Backwards-compatible alias
ALL_DEFAULT_ACCOUNTS = DEFAULT_ACCOUNTS

DEFAULT_COMMODITY = "$"
DEFAULT_COMMODITY_FORMAT = "$1,000.00"
