"""Extended tests for database CRUD: categories, budgets, audit log, backups."""

from __future__ import annotations

from datetime import date

from expenses_tracker.schemas import BudgetInput, CategoryInput, TransactionInput

# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


class TestCategoryCRUD:
    def test_add_category(self, db):
        cat = CategoryInput(name="Food", transaction_type="expense")
        cat_id = db.add_category(cat)
        assert isinstance(cat_id, int)
        assert cat_id >= 1

    def test_fetch_categories_returns_all(self, db):
        db.add_category(CategoryInput(name="Food", transaction_type="expense"))
        db.add_category(CategoryInput(name="Salary", transaction_type="income"))
        rows = db.fetch_categories()
        assert len(rows) == 2

    def test_fetch_categories_filter_by_type(self, db):
        db.add_category(CategoryInput(name="Food", transaction_type="expense"))
        db.add_category(CategoryInput(name="Salary", transaction_type="income"))
        expense_cats = db.fetch_categories(transaction_type="expense")
        assert len(expense_cats) == 1
        assert expense_cats[0]["name"] == "Food"

    def test_fetch_categories_active_only_false(self, db):
        db.add_category(CategoryInput(name="Old", transaction_type="expense", is_active=False))
        active = db.fetch_categories(active_only=True)
        all_cats = db.fetch_categories(active_only=False)
        assert len(active) == 0
        assert len(all_cats) == 1

    def test_update_category(self, db):
        cat_id = db.add_category(CategoryInput(name="Food", transaction_type="expense"))
        updated = db.update_category(cat_id, CategoryInput(name="Groceries", transaction_type="expense"))
        assert updated is True
        rows = db.fetch_categories()
        assert rows[0]["name"] == "Groceries"

    def test_update_missing_category_returns_false(self, db):
        updated = db.update_category(9999, CategoryInput(name="X", transaction_type="expense"))
        assert updated is False

    def test_delete_category(self, db):
        cat_id = db.add_category(CategoryInput(name="Food", transaction_type="expense"))
        assert db.delete_category(cat_id) is True
        assert db.fetch_categories() == []

    def test_delete_missing_category_returns_false(self, db):
        assert db.delete_category(9999) is False


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------


class TestBudgetCRUD:
    def test_add_budget(self, db):
        budget_id = db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        assert isinstance(budget_id, int)

    def test_add_budget_same_category_month_updates(self, db):
        id1 = db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        id2 = db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=600.0))
        assert id1 == id2
        rows = db.fetch_budgets()
        assert rows[0]["planned_amount"] == 600.0

    def test_fetch_budgets_filter_month(self, db):
        db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        db.add_budget(BudgetInput(category="Food", month="2025-02", planned_amount=600.0))
        rows = db.fetch_budgets(month="2025-01")
        assert len(rows) == 1
        assert rows[0]["month"] == "2025-01"

    def test_update_budget(self, db):
        b_id = db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        updated = db.update_budget(b_id, BudgetInput(category="Food", month="2025-01", planned_amount=700.0))
        assert updated is True
        assert db.fetch_budgets()[0]["planned_amount"] == 700.0

    def test_update_missing_budget_returns_false(self, db):
        assert db.update_budget(9999, BudgetInput(category="X", month="2025-01", planned_amount=1.0)) is False

    def test_delete_budget(self, db):
        b_id = db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        assert db.delete_budget(b_id) is True
        assert db.fetch_budgets() == []

    def test_delete_missing_budget_returns_false(self, db):
        assert db.delete_budget(9999) is False

    def test_get_budget_vs_actual(self, db):
        db.add_budget(BudgetInput(category="Food", month="2025-01", planned_amount=500.0))
        db.add_transaction(TransactionInput(200.0, "expense", "Food", date(2025, 1, 10)))
        db.add_transaction(TransactionInput(100.0, "expense", "Food", date(2025, 1, 15)))
        rows = db.get_budget_vs_actual("2025-01")
        assert len(rows) == 1
        assert rows[0]["planned"] == 500.0
        assert rows[0]["actual"] == 300.0
        assert rows[0]["difference"] == 200.0

    def test_get_budget_vs_actual_no_budget(self, db):
        db.add_transaction(TransactionInput(200.0, "expense", "Food", date(2025, 1, 10)))
        rows = db.get_budget_vs_actual("2025-01")
        assert len(rows) == 1
        assert rows[0]["planned"] == 0.0
        assert rows[0]["actual"] == 200.0


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLogCRUD:
    def test_log_audit_creates_entry(self, db):
        db.initialize()
        db.log_audit("create", entity="transaction", entity_id=1, details="test")
        entries = db.get_audit_log(limit=10)
        assert len(entries) == 1
        assert entries[0]["action"] == "create"

    def test_get_audit_log_filter_by_action(self, db):
        db.log_audit("create", entity="transaction", entity_id=1)
        db.log_audit("delete", entity="transaction", entity_id=2)
        creates = db.get_audit_log(limit=10, action="create")
        assert len(creates) == 1
        assert creates[0]["action"] == "create"

    def test_get_audit_log_empty(self, db):
        assert db.get_audit_log(limit=10) == []


# ---------------------------------------------------------------------------
# Backup wrappers
# ---------------------------------------------------------------------------


class TestBackupWrappers:
    def test_create_backup_wrapper(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        db.initialize()
        path = db.create_backup()
        assert path.exists()

    def test_list_backups_wrapper(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        db.initialize()
        db.create_backup()
        backups = db.list_backups()
        assert len(backups) >= 1

    def test_restore_backup_wrapper(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        db.initialize()
        db.add_transaction(TransactionInput(100.0, "income", "Salary", date(2025, 1, 1)))
        backup = db.create_backup()
        db.add_transaction(TransactionInput(50.0, "expense", "Food", date(2025, 1, 2)))
        db.restore_backup(backup.name)
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 1
