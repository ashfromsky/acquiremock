import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa


def _make_alembic_config(db_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_head_on_fresh_sqlite_db(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh_migrated.db"
    async_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", async_url)

    cfg = _make_alembic_config(async_url)
    command.upgrade(cfg, "head")

    sync_engine = sa.create_engine(f"sqlite:///{db_file}")
    try:
        inspector = sa.inspect(sync_engine)
        tables = set(inspector.get_table_names())
        assert {
            "payments",
            "successful_operations",
            "saved_cards",
            "webhook_logs",
            "admin_sessions",
            "idempotency_keys",
            "auth_challenges",
            "alembic_version",
        }.issubset(tables)

        payment_cols = {c["name"] for c in inspector.get_columns("payments")}
        assert {
            "otp_attempts",
            "otp_expires_at",
            "otp_resend_count",
            "webhook_next_attempt_at",
            "webhook_locked_until",
        }.issubset(payment_cols)

        payment_indexes = {idx["name"]: idx for idx in inspector.get_indexes("payments")}
        assert payment_indexes["ix_payments_idempotency_key"]["unique"] in (1, True)
    finally:
        sync_engine.dispose()


def test_alembic_upgrade_from_v1_preserves_existing_payment_data(tmp_path, monkeypatch):
    db_file = tmp_path / "legacy_upgrade.db"
    async_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", async_url)

    cfg = _make_alembic_config(async_url)
    command.upgrade(cfg, "0001_initial")

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            INSERT INTO payments (
                id, amount, reference, webhook_url, redirect_url, status,
                webhook_attempts, created_at, updated_at, expires_at
            ) VALUES (
                'legacy-pay-1', 25000.0, 'ORD-LEGACY-1',
                'https://example.com/hook', 'https://example.com/ok',
                'paid', 1, '2026-01-01 00:00:00', '2026-01-01 00:01:00', '2026-01-01 00:15:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO successful_operations (
                payment_id, email, amount, reference, card_mask, redirect_url, created_at
            ) VALUES (
                'legacy-pay-1', 'legacy@example.com', 25000.0, 'ORD-LEGACY-1',
                '**** 4444', 'https://example.com/ok', '2026-01-01 00:01:00'
            )
            """
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with sqlite3.connect(db_file) as conn:
        row = conn.execute(
            "SELECT amount, otp_attempts, otp_resend_count FROM payments WHERE id = 'legacy-pay-1'"
        ).fetchone()
        assert row == (25000, 0, 0)

        op_row = conn.execute(
            "SELECT amount FROM successful_operations WHERE payment_id = 'legacy-pay-1'"
        ).fetchone()
        assert op_row == (25000,)
