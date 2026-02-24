"""Accounts screen -- account hierarchy and detail view."""

from __future__ import annotations

import json
import logging

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from ws_accounting.core.hledger import (
    HLedgerError,
    HLedgerGateway,
    HLedgerNotFoundError,
)
from ws_accounting.core.parser import (
    parse_balance_report,
    parse_register,
)
from ws_accounting.widgets.account_tree import AccountTree
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)


class AccountsScreen(Screen):
    """Account hierarchy browser with detail pane."""

    CSS_PATH = "../styles/accounts.tcss"

    BINDINGS = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gateway: HLedgerGateway | None = None
        self._selected_account: str | None = None

    def compose(self) -> ComposeResult:
        yield NavHeader()

        with Horizontal(id="accounts-layout"):
            # Left pane: account tree
            with Vertical(id="accounts-tree-pane"):
                yield Label(
                    "Account Hierarchy",
                    classes="section-title",
                )
                yield AccountTree(id="account-tree")
                with Horizontal(id="account-actions"):
                    yield Button(
                        "Add Account",
                        id="btn-add-account",
                        variant="primary",
                    )
                    yield Button(
                        "Reconcile",
                        id="btn-reconcile",
                        variant="default",
                    )

            # Right pane: account detail
            with Vertical(id="accounts-detail-pane"):
                yield Label(
                    "Select an account",
                    id="detail-title",
                    classes="section-title",
                )
                yield Container(id="detail-balance")
                yield Label(
                    "Recent Transactions",
                    id="detail-txns-title",
                    classes="section-title",
                )
                yield Container(id="detail-txns")

        # Empty state overlay (hidden when data exists)
        yield Static(
            "No accounts configured.\n\n"
            "Import a CSV or add transactions to create accounts.\n"
            "Use Ctrl+3 to open CSV Import.",
            id="accounts-empty-state",
            classes="muted-text",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Load account list when screen is mounted."""
        self.query_one(NavHeader).set_active("accounts")
        # Grab the gateway from the app
        if self._gateway is None and hasattr(self.app, "gateway"):
            self._gateway = self.app.gateway
        if self._gateway is not None:
            self._load_accounts()

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Set the hledger gateway and trigger a reload."""
        self._gateway = gateway
        if self.is_mounted:
            self._load_accounts()

    def _load_accounts(self) -> None:
        """Spawn a worker to fetch the account list."""
        self.run_worker(
            self._fetch_accounts(),
            name="accounts-list",
            exclusive=True,
        )

    async def _fetch_accounts(self) -> None:
        """Fetch account list from hledger and populate the tree."""
        if self._gateway is None:
            self._show_empty_state()
            return

        try:
            await self._gateway.check_installation()
        except (HLedgerNotFoundError, HLedgerError) as exc:
            log.warning("hledger not available: %s", exc)
            self._show_empty_state()
            return

        try:
            accounts = await self._gateway.accounts()
            tree = self.query_one("#account-tree", AccountTree)
            tree.load_accounts(accounts)
            if accounts:
                self._hide_empty_state()
            else:
                self._show_empty_state()
        except Exception as exc:
            log.warning("Failed to load accounts: %s", exc)
            self._show_empty_state()

    def on_account_tree_account_selected(
        self, event: AccountTree.AccountSelected
    ) -> None:
        """When an account is selected, load its detail."""
        self._selected_account = event.account
        title = self.query_one("#detail-title", Label)
        title.update(event.account)
        self._load_detail(event.account)

    def _load_detail(self, account: str) -> None:
        """Spawn a worker to fetch detail for the selected account."""
        self.run_worker(
            self._fetch_detail(account),
            name="account-detail",
            exclusive=True,
        )

    async def _fetch_detail(self, account: str) -> None:
        """Fetch balance and recent transactions for an account."""
        if self._gateway is None:
            return

        # Fetch balance
        await self._fetch_account_balance(account)

        # Fetch recent transactions
        await self._fetch_account_txns(account)

    async def _fetch_account_balance(
        self, account: str
    ) -> None:
        """Fetch and display the balance for a single account."""
        container = self.query_one("#detail-balance", Container)
        container.remove_children()

        try:
            raw = await self._gateway.balance(
                accounts=[account],
            )
            data = json.loads(raw)
            balances = parse_balance_report(data)

            if balances:
                bal = balances[0]
                q = bal.balance.quantity
                c = bal.balance.commodity
                sign = "+" if q >= 0 else "-"
                text = f"Balance: {sign}{c}{abs(q):,.2f}"
            else:
                text = "Balance: $0.00"

            container.mount(
                Static(text, id="balance-display")
            )
        except Exception as exc:
            log.debug(
                "Failed to fetch balance for %s: %s",
                account,
                exc,
            )
            container.mount(
                Static(
                    "Balance unavailable",
                    classes="muted-text",
                )
            )

    async def _fetch_account_txns(
        self, account: str
    ) -> None:
        """Fetch and display recent transactions for an account."""
        container = self.query_one("#detail-txns", Container)
        container.remove_children()

        try:
            raw = await self._gateway.register(
                query=f"acct:{account}",
                limit=10,
            )
            data = json.loads(raw)
            transactions = parse_register(data)

            if not transactions:
                container.mount(
                    Static(
                        "No transactions",
                        classes="muted-text",
                    )
                )
                return

            for txn in reversed(transactions):
                desc = txn.description
                if txn.payee:
                    desc = f"{txn.payee} | {desc}"
                date_str = txn.date.isoformat()

                # Find amount for this specific account
                amt_str = ""
                for posting in txn.postings:
                    if (
                        posting.amount
                        and posting.account == account
                    ):
                        q = posting.amount.quantity
                        c = posting.amount.commodity
                        sign = "+" if q >= 0 else "-"
                        amt_str = (
                            f"{sign}{c}{abs(q):,.2f}"
                        )
                        break

                row = (
                    f"{date_str}  {desc:<30s}  {amt_str}"
                )
                container.mount(
                    Static(row, classes="txn-row")
                )
        except Exception as exc:
            log.debug(
                "Failed to fetch txns for %s: %s",
                account,
                exc,
            )
            container.mount(
                Static(
                    "Transaction data unavailable",
                    classes="muted-text",
                )
            )

    def _show_empty_state(self) -> None:
        """Show the empty state message and hide the main layout."""
        try:
            empty = self.query_one("#accounts-empty-state")
            empty.display = True
            layout = self.query_one("#accounts-layout")
            layout.display = False
        except Exception:
            pass

    def _hide_empty_state(self) -> None:
        """Hide the empty state message and show the main layout."""
        try:
            empty = self.query_one("#accounts-empty-state")
            empty.display = False
            layout = self.query_one("#accounts-layout")
            layout.display = True
        except Exception:
            pass

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        """Handle action button presses."""
        if event.button.id == "btn-add-account":
            self.notify("Add account -- coming soon")
        elif event.button.id == "btn-reconcile":
            if self._selected_account:
                self.notify(
                    f"Reconcile {self._selected_account}"
                    " -- coming soon"
                )
            else:
                self.notify("Select an account first")
