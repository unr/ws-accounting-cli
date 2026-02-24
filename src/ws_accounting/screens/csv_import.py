"""CSV Import wizard -- 4-step linear import flow."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.screen import Screen
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    Label,
    Select,
    Static,
)

from ws_accounting.config.defaults import (
    ALL_DEFAULT_ACCOUNTS,
)
from ws_accounting.core.csv_import import (
    CSVStructure,
    DuplicateResult,
    TransferCandidate,
    check_duplicates,
    compute_import_hash,
    detect_structure,
    detect_transfers,
    parse_csv_rows,
)
from ws_accounting.core.hledger import HLedgerGateway
from ws_accounting.core.journal import write_transactions
from ws_accounting.core.models import (
    Amount,
    CategorizedTransaction,
    Posting,
    Transaction,
    TransactionStatus,
)
from ws_accounting.widgets.category_picker import CategoryPicker
from ws_accounting.widgets.import_stepper import ImportStepper
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)


class CSVImportScreen(Screen):
    """CSV import wizard with 4 linear steps."""

    CSS_PATH = "../styles/csv_import.tcss"
    BINDINGS = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._gateway: HLedgerGateway | None = None
        self._csv_path: Path | None = None
        self._structure: CSVStructure | None = None
        self._parsed_rows: list[dict] = []
        self._categorizations: list[CategorizedTransaction] = []
        self._dup_results: list[DuplicateResult] = []
        self._transfer_candidates: list[TransferCandidate] = []
        self._selected_account: str = "assets:bank:checking"
        self._import_count: int = 0
        self._dup_count: int = 0
        self._transfer_count: int = 0

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Inject the hledger gateway."""
        self._gateway = gateway

    def compose(self) -> ComposeResult:
        yield NavHeader()
        yield ImportStepper(id="import-stepper")
        with ContentSwitcher(
            id="import-switcher", initial="step-file"
        ):
            # Step 1: File Selection
            with Vertical(id="step-file"):
                yield Label(
                    "Step 1: Select CSV File",
                    classes="step-title",
                )
                yield Label(
                    "Enter the path to your bank CSV export.",
                    classes="step-description",
                )
                yield Input(
                    placeholder="Path to CSV file...",
                    id="csv-path-input",
                )
                yield Label(
                    "Bank profile (optional):",
                    classes="field-label",
                )
                yield Select(
                    [(
                        "-- New Profile --",
                        "__new__",
                    )],
                    id="profile-select",
                    allow_blank=True,
                    prompt="Select existing profile",
                )
                yield Static(id="file-error", classes="error-text")
                with Horizontal(classes="step-buttons"):
                    yield Button(
                        "Next",
                        variant="primary",
                        id="btn-file-next",
                    )

            # Step 2: Column Mapping
            with Vertical(id="step-mapping"):
                yield Label(
                    "Step 2: Map Columns",
                    classes="step-title",
                )
                yield Label(
                    "Confirm or adjust detected column mappings.",
                    classes="step-description",
                )
                yield Static(
                    id="detected-info",
                    classes="info-text",
                )
                with Container(id="mapping-fields"):
                    yield Label(
                        "Date column:", classes="field-label"
                    )
                    yield Select(
                        [],
                        id="date-col-select",
                        allow_blank=True,
                        prompt="Select date column",
                    )
                    yield Label(
                        "Description column:",
                        classes="field-label",
                    )
                    yield Select(
                        [],
                        id="desc-col-select",
                        allow_blank=True,
                        prompt="Select description column",
                    )
                    yield Label(
                        "Amount column:", classes="field-label"
                    )
                    yield Select(
                        [],
                        id="amount-col-select",
                        allow_blank=True,
                        prompt="Select amount column",
                    )
                    yield Label(
                        "Target account:", classes="field-label"
                    )
                    yield CategoryPicker(
                        categories=list(ALL_DEFAULT_ACCOUNTS),
                        placeholder="e.g., assets:bank:checking",
                        id="account-picker",
                    )
                with Horizontal(classes="step-buttons"):
                    yield Button(
                        "Back",
                        variant="default",
                        id="btn-mapping-back",
                    )
                    yield Button(
                        "Next",
                        variant="primary",
                        id="btn-mapping-next",
                    )

            # Step 3: Review + AI categorization
            with Vertical(id="step-review"):
                yield Label(
                    "Step 3: Review Transactions",
                    classes="step-title",
                )
                yield Label(
                    "Review detected transactions. "
                    "AI categories are shown where available.",
                    classes="step-description",
                )
                with Horizontal(id="review-actions"):
                    yield Button(
                        "Accept All High-Confidence",
                        variant="success",
                        id="btn-accept-high",
                    )
                    yield Static(id="review-stats")
                yield ScrollableContainer(
                    DataTable(id="review-table"),
                    id="review-scroll",
                )
                with Horizontal(classes="step-buttons"):
                    yield Button(
                        "Back",
                        variant="default",
                        id="btn-review-back",
                    )
                    yield Button(
                        "Import Selected",
                        variant="primary",
                        id="btn-import",
                    )

            # Step 4: Import Summary
            with Vertical(id="step-summary"):
                yield Label(
                    "Step 4: Import Complete",
                    classes="step-title",
                )
                yield Static(
                    id="summary-text", classes="summary-card"
                )
                with Horizontal(classes="step-buttons"):
                    yield Button(
                        "Done",
                        variant="primary",
                        id="btn-done",
                    )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the review table columns."""
        self.query_one(NavHeader).set_active("csv_import")
        # Grab the gateway from the app if not already set
        if self._gateway is None and hasattr(self.app, "gateway"):
            self._gateway = self.app.gateway
        table = self.query_one("#review-table", DataTable)
        table.add_columns(
            "Row",
            "Date",
            "Description",
            "Amount",
            "Category",
            "Confidence",
            "Flags",
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to their handlers."""
        button_id = event.button.id
        if button_id == "btn-file-next":
            self._handle_file_next()
        elif button_id == "btn-mapping-back":
            self._go_to_step(0)
        elif button_id == "btn-mapping-next":
            self._handle_mapping_next()
        elif button_id == "btn-review-back":
            self._go_to_step(1)
        elif button_id == "btn-accept-high":
            self._accept_high_confidence()
        elif button_id == "btn-import":
            self._handle_import()
        elif button_id == "btn-done":
            self._handle_done()

    # ------------------------------------------------------------------
    # Step 1: File selection
    # ------------------------------------------------------------------

    def _handle_file_next(self) -> None:
        """Validate the CSV path and advance to step 2."""
        path_input = self.query_one(
            "#csv-path-input", Input
        )
        error_widget = self.query_one(
            "#file-error", Static
        )

        raw_path = path_input.value.strip()
        if not raw_path:
            error_widget.update("Please enter a CSV file path.")
            return

        csv_path = Path(raw_path).expanduser().resolve()
        if not csv_path.exists():
            error_widget.update(
                f"File not found: {csv_path}"
            )
            return
        if not csv_path.suffix.lower() == ".csv":
            error_widget.update(
                "File must have a .csv extension."
            )
            return

        error_widget.update("")
        self._csv_path = csv_path

        try:
            self._structure = detect_structure(csv_path)
        except Exception as exc:
            error_widget.update(
                f"Failed to detect CSV structure: {exc}"
            )
            return

        self._populate_mapping_step()
        self._go_to_step(1)

    def _populate_mapping_step(self) -> None:
        """Fill the column mapping dropdowns from detected structure."""
        if self._structure is None:
            return

        headers = self._structure.headers
        options = [
            (f"{i}: {header}", i)
            for i, header in enumerate(headers)
        ]

        date_sel = self.query_one("#date-col-select", Select)
        desc_sel = self.query_one("#desc-col-select", Select)
        amount_sel = self.query_one(
            "#amount-col-select", Select
        )

        date_sel.set_options(options)
        desc_sel.set_options(options)
        amount_sel.set_options(options)

        date_sel.value = self._structure.date_column
        desc_sel.value = self._structure.description_column
        amount_sel.value = self._structure.amount_column

        # Show detected info
        info = self.query_one("#detected-info", Static)
        n_cols = len(headers)
        info.update(
            f"Detected {n_cols} columns, "
            f"delimiter='{self._structure.delimiter}'"
        )

    # ------------------------------------------------------------------
    # Step 2: Column mapping
    # ------------------------------------------------------------------

    def _handle_mapping_next(self) -> None:
        """Apply column mapping selections and parse the CSV."""
        if self._structure is None or self._csv_path is None:
            return

        date_sel = self.query_one("#date-col-select", Select)
        desc_sel = self.query_one("#desc-col-select", Select)
        amount_sel = self.query_one(
            "#amount-col-select", Select
        )
        account_picker = self.query_one(
            "#account-picker", CategoryPicker
        )

        if date_sel.value is not Select.BLANK:
            self._structure.date_column = int(date_sel.value)
        if desc_sel.value is not Select.BLANK:
            self._structure.description_column = int(
                desc_sel.value
            )
        if amount_sel.value is not Select.BLANK:
            self._structure.amount_column = int(
                amount_sel.value
            )

        if account_picker.value:
            self._selected_account = account_picker.value

        # Parse CSV rows
        try:
            self._parsed_rows = parse_csv_rows(
                self._csv_path, self._structure
            )
        except Exception as exc:
            self.notify(
                f"Error parsing CSV: {exc}",
                severity="error",
            )
            return

        if not self._parsed_rows:
            self.notify(
                "No data rows found in CSV.",
                severity="warning",
            )
            return

        # Run duplicate detection
        existing_hashes: set[str] = set()
        app = self.app
        if hasattr(app, "database") and app.database is not None:
            from ws_accounting.db.queries import check_import_hash

            # Build set of existing hashes by checking each row
            for row in self._parsed_rows:
                if all(
                    k in row
                    for k in ("date", "amount", "description")
                ):
                    h = compute_import_hash(
                        row["date"],
                        row["description"],
                        row["amount"],
                    )
                    if check_import_hash(app.database, h):
                        existing_hashes.add(h)

        valid_rows = [
            r
            for r in self._parsed_rows
            if all(
                k in r
                for k in ("date", "amount", "description")
            )
        ]
        self._dup_results = check_duplicates(
            valid_rows, existing_hashes
        )

        # Run transfer detection
        self._transfer_candidates = detect_transfers(valid_rows)

        # Populate the review table
        self._populate_review_table()

        # Run AI categorization in background
        self.run_worker(
            self._run_categorization(),
            name="ai-categorize",
            exclusive=True,
        )

        self._go_to_step(2)

    def _populate_review_table(self) -> None:
        """Fill the review DataTable with parsed rows."""
        table = self.query_one("#review-table", DataTable)
        table.clear()

        # Build sets for quick lookup
        dup_indices = {
            i
            for i, d in enumerate(self._dup_results)
            if d.is_duplicate
        }
        transfer_indices: set[int] = set()
        for tc in self._transfer_candidates:
            transfer_indices.add(tc.from_idx)
            transfer_indices.add(tc.to_idx)

        valid_rows = [
            r
            for r in self._parsed_rows
            if all(
                k in r
                for k in ("date", "amount", "description")
            )
        ]

        dup_total = 0
        for i, row in enumerate(valid_rows):
            flags: list[str] = []
            if i in dup_indices:
                flags.append("DUP")
                dup_total += 1
            if i in transfer_indices:
                flags.append("XFER")

            category = "..."
            confidence = "..."
            if i < len(self._categorizations):
                cat = self._categorizations[i]
                category = cat.suggested_account
                confidence = f"{cat.confidence:.0%}"

            table.add_row(
                str(i + 1),
                row.get("date", ""),
                row.get("description", "")[:40],
                row.get("amount", ""),
                category,
                confidence,
                " ".join(flags) if flags else "",
            )

        # Update stats
        stats = self.query_one("#review-stats", Static)
        stats.update(
            f"{len(valid_rows)} transactions | "
            f"{dup_total} duplicates | "
            f"{len(self._transfer_candidates)} transfers"
        )

    async def _run_categorization(self) -> None:
        """Run AI categorization on parsed rows."""
        app = self.app
        if (
            not hasattr(app, "database")
            or app.database is None
        ):
            return

        try:
            from ws_accounting.ai.categorizer import Categorizer

            categorizer = Categorizer(
                db=app.database, provider=None
            )

            valid_rows = [
                r
                for r in self._parsed_rows
                if all(
                    k in r
                    for k in (
                        "date",
                        "amount",
                        "description",
                    )
                )
            ]

            txn_dicts: list[dict] = []
            for row in valid_rows:
                try:
                    amt = Decimal(
                        row["amount"]
                        .replace(",", "")
                        .replace("$", "")
                    )
                except (InvalidOperation, ValueError):
                    amt = Decimal("0")
                txn_dicts.append(
                    {
                        "description": row["description"],
                        "amount": amt,
                        "date": row["date"],
                    }
                )

            if txn_dicts:
                self._categorizations = (
                    await categorizer.categorize_batch(txn_dicts)
                )
                # Refresh the review table with categories
                self.call_from_thread(
                    self._populate_review_table
                )
        except Exception as exc:
            log.warning("AI categorization failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 3: Review
    # ------------------------------------------------------------------

    def _accept_high_confidence(self) -> None:
        """Mark all high-confidence categorizations as accepted."""
        self.notify(
            "High-confidence categorizations accepted.",
            severity="information",
        )

    def _handle_import(self) -> None:
        """Build transactions and write to journal."""
        if self._gateway is None:
            self.notify(
                "No hledger gateway configured.",
                severity="error",
            )
            return

        valid_rows = [
            r
            for r in self._parsed_rows
            if all(
                k in r
                for k in ("date", "amount", "description")
            )
        ]

        # Build set of duplicate indices to skip
        dup_indices = {
            i
            for i, d in enumerate(self._dup_results)
            if d.is_duplicate
        }

        transactions: list[Transaction] = []
        imported_hashes: list[str] = []
        skipped = 0

        for i, row in enumerate(valid_rows):
            if i in dup_indices:
                skipped += 1
                continue

            # Parse amount
            try:
                amt = Decimal(
                    row["amount"]
                    .replace(",", "")
                    .replace("$", "")
                )
            except (InvalidOperation, ValueError):
                log.warning(
                    "Skipping row %d: bad amount '%s'",
                    i,
                    row["amount"],
                )
                skipped += 1
                continue

            # Parse date
            try:
                txn_date = date.fromisoformat(row["date"])
            except ValueError:
                log.warning(
                    "Skipping row %d: bad date '%s'",
                    i,
                    row["date"],
                )
                skipped += 1
                continue

            # Determine category account
            category = "expenses:miscellaneous"
            if i < len(self._categorizations):
                category = (
                    self._categorizations[i].suggested_account
                )

            # Build the transaction
            postings = (
                Posting(
                    account=self._selected_account,
                    amount=Amount(
                        quantity=amt, commodity="$"
                    ),
                ),
                Posting(
                    account=category,
                    amount=None,  # auto-balance
                ),
            )

            txn = Transaction(
                date=txn_date,
                status=TransactionStatus.CLEARED,
                description=row["description"],
                postings=postings,
            )
            transactions.append(txn)

            # Compute hash for dedup tracking
            h = compute_import_hash(
                row["date"], row["description"], row["amount"]
            )
            imported_hashes.append(h)

        if not transactions:
            self.notify(
                "No transactions to import "
                "(all duplicates or errors).",
                severity="warning",
            )
            return

        # Write to journal
        try:
            journal_path = self._gateway.journal_path
            import_file = (
                journal_path.parent / "imports" / (
                    self._csv_path.stem + ".journal"
                    if self._csv_path
                    else "import.journal"
                )
            )
            import_file.parent.mkdir(
                parents=True, exist_ok=True
            )
            write_transactions(
                import_file, transactions, append=True
            )

            # Update includes in main journal
            from ws_accounting.core.journal import (
                update_includes,
            )

            relative_import = (
                f"imports/{import_file.name}"
            )
            update_includes(journal_path, relative_import)
        except Exception as exc:
            self.notify(
                f"Failed to write journal: {exc}",
                severity="error",
            )
            return

        # Store import hashes in database
        app = self.app
        if hasattr(app, "database") and app.database is not None:
            try:
                from ws_accounting.db.queries import (
                    record_import,
                    store_import_hashes,
                )

                history = record_import(
                    app.database,
                    csv_filename=(
                        self._csv_path.name
                        if self._csv_path
                        else "unknown.csv"
                    ),
                    profile_id=0,
                    txn_count=len(transactions),
                    duplicate_count=skipped,
                )
                if history.id is not None:
                    store_import_hashes(
                        app.database,
                        imported_hashes,
                        history.id,
                    )
            except Exception as exc:
                log.warning(
                    "Failed to record import history: %s", exc
                )

        self._import_count = len(transactions)
        self._dup_count = skipped
        self._transfer_count = len(
            self._transfer_candidates
        )

        self.notify(
            f"Imported {self._import_count} transactions"
            f" ({self._dup_count} duplicates skipped).",
            title="Import Complete",
        )

        # Show summary
        self._populate_summary()
        self._go_to_step(3)

    # ------------------------------------------------------------------
    # Step 4: Summary
    # ------------------------------------------------------------------

    def _populate_summary(self) -> None:
        """Fill the summary display with import results."""
        summary = self.query_one("#summary-text", Static)
        lines = [
            f"Imported: {self._import_count} transactions",
            f"Duplicates skipped: {self._dup_count}",
            f"Transfers detected: {self._transfer_count}",
        ]
        if self._csv_path:
            lines.insert(0, f"File: {self._csv_path.name}")
        lines.append("")
        lines.append(
            "Transactions have been written to your journal."
        )
        summary.update("\n".join(lines))

    def _handle_done(self) -> None:
        """Return to the dashboard."""
        try:
            self.app.switch_mode("dashboard")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _go_to_step(self, step: int) -> None:
        """Switch to a wizard step."""
        stepper = self.query_one(
            "#import-stepper", ImportStepper
        )
        stepper.set_step(step)

        switcher = self.query_one(
            "#import-switcher", ContentSwitcher
        )
        step_ids = [
            "step-file",
            "step-mapping",
            "step-review",
            "step-summary",
        ]
        if 0 <= step < len(step_ids):
            switcher.current = step_ids[step]
