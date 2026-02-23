"""Default chart of accounts, categories, and commodity settings."""

DEFAULT_CATEGORIES: list[str] = [
    "expenses:food:groceries",
    "expenses:food:dining",
    "expenses:housing:rent",
    "expenses:housing:utilities",
    "expenses:transportation:gas",
    "expenses:transportation:transit",
    "expenses:health:medical",
    "expenses:health:insurance",
    "expenses:entertainment",
    "expenses:shopping:clothing",
    "expenses:shopping:general",
    "expenses:subscriptions",
    "expenses:education",
    "expenses:personal care",
    "expenses:gifts",
    "expenses:travel",
    "expenses:taxes:federal",
    "expenses:taxes:state",
    "expenses:charitable:donations",
    "expenses:fees:bank",
    "expenses:miscellaneous",
]

DEFAULT_INCOME_CATEGORIES: list[str] = [
    "income:salary",
    "income:freelance",
    "income:interest",
    "income:refunds",
]

DEFAULT_ASSET_ACCOUNTS: list[str] = [
    "assets:bank:checking",
    "assets:bank:savings",
    "assets:cash",
    "assets:investments",
]

DEFAULT_LIABILITY_ACCOUNTS: list[str] = [
    "liabilities:credit card",
    "liabilities:loans",
]

ALL_DEFAULT_ACCOUNTS: list[str] = (
    DEFAULT_ASSET_ACCOUNTS
    + DEFAULT_LIABILITY_ACCOUNTS
    + DEFAULT_INCOME_CATEGORIES
    + DEFAULT_CATEGORIES
    + ["equity:opening balances"]
)

DEFAULT_COMMODITY = "$"
DEFAULT_COMMODITY_FORMAT = "$1,000.00"
