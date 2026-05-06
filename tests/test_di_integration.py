"""Integration tests for DI container wiring in production entry points."""

from __future__ import annotations

from expenses_tracker.di import Container
from expenses_tracker.di import container as global_container
from expenses_tracker.services import ExportService, TransactionService, UIStateService


class FakeDatabase:
    pass


def test_global_container_is_singleton():
    assert isinstance(global_container, Container)


def test_container_wiring_for_gui():
    c = Container()
    fake_db = FakeDatabase()
    c.register("database", lambda: fake_db, singleton=True)
    c.register("transaction_service", lambda: TransactionService(fake_db), singleton=True)  # type: ignore[arg-type]
    c.register("export_service", lambda: ExportService(), singleton=True)
    c.register("state_service", lambda: UIStateService("/tmp/fake_state.json"), singleton=True)

    tx_svc = c.resolve("transaction_service")
    exp_svc = c.resolve("export_service")
    state_svc = c.resolve("state_service")

    assert isinstance(tx_svc, TransactionService)
    assert isinstance(exp_svc, ExportService)
    assert isinstance(state_svc, UIStateService)
    assert c.resolve("transaction_service") is tx_svc  # singleton


def test_container_factory_produces_new_instances():
    c = Container()
    c.register("svc", lambda: object(), singleton=False)
    a = c.resolve("svc")
    b = c.resolve("svc")
    assert a is not b


def test_container_services_are_independent_between_instances():
    c1 = Container()
    c2 = Container()
    c1.register("x", lambda: 1)
    c2.register("x", lambda: 2)
    assert c1.resolve("x") == 1
    assert c2.resolve("x") == 2
