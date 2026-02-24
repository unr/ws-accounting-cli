"""Account hierarchy tree widget."""

from decimal import Decimal

from textual.message import Message
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

    class AccountSelected(Message):
        """Fired when a leaf account is selected."""

        def __init__(self, account: str) -> None:
            super().__init__()
            self.account = account

    def __init__(self, label: str = "Accounts", **kwargs) -> None:
        super().__init__(label, **kwargs)

    def load_accounts(self, data: dict[str, Decimal] | list[str]) -> None:
        """Build tree from account:balance mapping or a list of account names.

        Accepts either:
          - dict[str, Decimal]: account -> balance mapping
          - list[str]: flat list of account names (balances shown as 0)
        """
        self.clear()
        nodes: dict[str, object] = {}

        # Normalize to dict
        if isinstance(data, list):
            balances: dict[str, Decimal] = {acct: Decimal("0") for acct in data}
        else:
            balances = data

        for account, balance in sorted(balances.items()):
            parts = account.split(":")
            parent = self.root
            for i, part in enumerate(parts):
                path = ":".join(parts[: i + 1])
                if path not in nodes:
                    if path == account and balance != Decimal("0"):
                        label = f"{part}  ${abs(balance):,.2f}"
                    else:
                        label = part
                    nodes[path] = parent.add(label, data={"account": path, "balance": balance})
                parent = nodes[path]
        self.root.expand_all()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Post AccountSelected when a tree node is selected."""
        node_data = event.node.data
        if node_data and isinstance(node_data, dict) and "account" in node_data:
            self.post_message(self.AccountSelected(node_data["account"]))
