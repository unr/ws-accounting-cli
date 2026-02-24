"""Account hierarchy tree widget."""

from decimal import Decimal

from textual.widgets import Tree


class AccountTree(Tree):
    """Tree widget displaying account hierarchy with inline balances."""

    DEFAULT_CSS = """
    AccountTree {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("h", "toggle_node", "Collapse"),
        ("l", "toggle_node", "Expand"),
        ("space", "toggle_node", "Toggle"),
    ]

    def __init__(self, label: str = "Accounts", **kwargs) -> None:
        super().__init__(label, **kwargs)

    def load_accounts(self, balances: dict[str, Decimal]) -> None:
        """Build tree from account:balance mapping."""
        self.clear()
        nodes: dict[str, object] = {}
        for account, balance in sorted(balances.items()):
            parts = account.split(":")
            parent = self.root
            for i, part in enumerate(parts):
                path = ":".join(parts[: i + 1])
                if path not in nodes:
                    if path == account:
                        label = f"{part}  ${abs(balance):,.2f}"
                    else:
                        label = part
                    nodes[path] = parent.add(label, data={"account": path, "balance": balance})
                parent = nodes[path]
        self.root.expand_all()
