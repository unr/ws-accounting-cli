"""Tree widget for displaying hledger account hierarchy."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree
from textual.widgets._tree import TreeNode


class AccountTree(Tree[str]):
    """Tree widget that displays the hledger account hierarchy.

    Each node stores the full account name as its data.
    The tree is built from a flat list of colon-separated account names.
    """

    DEFAULT_CSS = """
    AccountTree {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    class AccountSelected(Message):
        """Fired when the user selects an account in the tree."""

        def __init__(self, account: str) -> None:
            self.account = account
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__("Accounts", **kwargs)

    def load_accounts(self, accounts: list[str]) -> None:
        """Build the tree from a flat list of account names.

        Account names are colon-separated, e.g.:
            assets:bank:checking
            assets:bank:savings
            expenses:food:groceries
        """
        self.clear()
        root = self.root
        root.expand()

        # Build a nested dict to represent the hierarchy
        hierarchy: dict = {}
        for account in sorted(accounts):
            parts = account.split(":")
            node = hierarchy
            for part in parts:
                if part not in node:
                    node[part] = {}
                node = node[part]

        # Recursively add nodes to the tree
        self._add_children(root, hierarchy, "")

    def _add_children(
        self,
        parent: TreeNode[str],
        children: dict,
        prefix: str,
    ) -> None:
        """Recursively add child nodes."""
        for name, subtree in sorted(children.items()):
            full_name = f"{prefix}:{name}" if prefix else name
            if subtree:
                # Has children -- add as expandable branch
                node = parent.add(name, data=full_name)
                node.expand()
                self._add_children(node, subtree, full_name)
            else:
                # Leaf node
                parent.add_leaf(name, data=full_name)

    def on_tree_node_selected(
        self, event: Tree.NodeSelected[str]
    ) -> None:
        """Post an AccountSelected message when a node is selected."""
        if event.node.data is not None:
            self.post_message(self.AccountSelected(event.node.data))
