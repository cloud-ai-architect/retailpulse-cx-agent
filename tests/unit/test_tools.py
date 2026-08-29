"""Tests for the tool layer.

Focused on the rules that have consequences for a customer: whether a return
is inside its window, and whether a refund is allowed to go through. Both are
decided in Python rather than by the model precisely so they can be tested
like this.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from src.tools import policy, price_compare, refund


class FakeOrderTable:
    """Enough of a DynamoDB Table for the policy lookup."""

    def __init__(self, item: dict[str, Any] | None) -> None:
        self._item = item

    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        return {"Item": self._item} if self._item else {}


def _order(days_ago: int, category: str = "apparel", **extra: Any) -> dict[str, Any]:
    stamp = datetime.now(UTC) - timedelta(days=days_ago, hours=1)
    return {
        "order_id": "ORD-1",
        "category": category,
        "total_inr": 2500,
        "created_at": stamp.isoformat(),
        **extra,
    }


def _patch_policy_table(monkeypatch: pytest.MonkeyPatch, item: dict[str, Any] | None) -> None:
    monkeypatch.setattr(policy, "ORDERS_TABLE", "orders")

    class FakeResource:
        @staticmethod
        def Table(_name: str) -> FakeOrderTable:  # noqa: N802
            return FakeOrderTable(item)

    import boto3

    monkeypatch.setattr(boto3, "resource", lambda _svc: FakeResource())


class TestReturnPolicy:
    """The window decision is a rule, not a judgement, which is why it lives
    in Python. It also derives the elapsed days itself: when that was a tool
    argument, the model supplied 3 for a 66-day-old order and a customer was
    told an ineligible return was eligible."""

    def test_apparel_inside_window_is_eligible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_policy_table(monkeypatch, _order(10))
        result = json.loads(policy.check_return_policy("ORD-1"))
        assert result["eligible"] is True
        assert result["window_days"] == 30
        assert result["days_since_purchase"] == 10

    def test_electronics_has_the_shorter_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 20 days is fine for apparel and too late for electronics.
        _patch_policy_table(monkeypatch, _order(20, "apparel"))
        assert json.loads(policy.check_return_policy("ORD-1"))["eligible"] is True
        _patch_policy_table(monkeypatch, _order(20, "electronics"))
        assert json.loads(policy.check_return_policy("ORD-1"))["eligible"] is False

    def test_the_age_comes_from_the_order_not_the_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The regression: a 66-day-old electronics order is not eligible, no
        # matter what a model might have believed about its age.
        _patch_policy_table(monkeypatch, _order(66, "electronics"))
        result = json.loads(policy.check_return_policy("ORD-1"))
        assert result["days_since_purchase"] == 66
        assert result["eligible"] is False

    def test_boundary_day_is_still_eligible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Inclusive: day 30 of a 30-day window has been met.
        _patch_policy_table(monkeypatch, _order(30, "apparel"))
        assert json.loads(policy.check_return_policy("ORD-1"))["eligible"] is True
        _patch_policy_table(monkeypatch, _order(31, "apparel"))
        assert json.loads(policy.check_return_policy("ORD-1"))["eligible"] is False

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("Laptop", "electronics"),
            ("mobile phone", "electronics"),
            ("Footwear", "apparel"),
            ("home goods", "standard"),
            ("", "standard"),
        ],
    )
    def test_category_mapping(
        self, category: str, expected: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_policy_table(monkeypatch, _order(1, category))
        assert json.loads(policy.check_return_policy("ORD-1"))["policy"] == expected

    def test_unknown_order_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_policy_table(monkeypatch, None)
        assert json.loads(policy.check_return_policy("NOPE"))["error"] == "order not found"

    def test_unusable_date_is_reported_not_guessed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_policy_table(monkeypatch, _order(1) | {"created_at": "not-a-date"})
        result = json.loads(policy.check_return_policy("ORD-1"))
        assert "error" in result
        assert "eligible" not in result

    def test_already_refunded_is_surfaced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_policy_table(monkeypatch, _order(5, status="refunded"))
        assert json.loads(policy.check_return_policy("ORD-1"))["already_refunded"] is True

    def test_conditions_are_returned_for_the_customer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_policy_table(monkeypatch, _order(1, "electronics"))
        result = json.loads(policy.check_return_policy("ORD-1"))
        assert any("restocking" in c for c in result["conditions"])


class FakeTable:
    """Enough of a DynamoDB Table for the refund guards."""

    def __init__(self, item: dict[str, Any] | None, update_error: Exception | None = None) -> None:
        self._item = item
        self._update_error = update_error
        self.updates: list[dict[str, Any]] = []

    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        return {"Item": self._item} if self._item else {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        if self._update_error is not None:
            raise self._update_error
        self.updates.append(kwargs)
        return {}


@pytest.fixture
def order() -> dict[str, Any]:
    return {"order_id": "ORD-1", "total_inr": 2500, "status": "delivered"}


def _patch_table(monkeypatch: pytest.MonkeyPatch, table: FakeTable) -> None:
    monkeypatch.setattr(refund, "ORDERS_TABLE", "orders")

    class FakeResource:
        @staticmethod
        def Table(_name: str) -> FakeTable:  # noqa: N802
            return table

    import boto3

    monkeypatch.setattr(boto3, "resource", lambda _svc: FakeResource())


class TestRefundGuards:
    def test_refuses_an_amount_over_the_order_total(
        self, monkeypatch: pytest.MonkeyPatch, order: dict[str, Any]
    ) -> None:
        table = FakeTable(order)
        _patch_table(monkeypatch, table)

        result = json.loads(refund.initiate_refund("ORD-1", 9999.0))
        assert result["error"] == "refund exceeds order total"
        # Crucially, nothing was written.
        assert table.updates == []

    def test_refuses_a_non_positive_amount(
        self, monkeypatch: pytest.MonkeyPatch, order: dict[str, Any]
    ) -> None:
        table = FakeTable(order)
        _patch_table(monkeypatch, table)
        assert "positive" in json.loads(refund.initiate_refund("ORD-1", 0))["error"]
        assert table.updates == []

    def test_refuses_an_unknown_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = FakeTable(None)
        _patch_table(monkeypatch, table)
        assert json.loads(refund.initiate_refund("NOPE", 100.0))["error"] == "order not found"

    def test_allows_a_refund_up_to_the_full_total(
        self, monkeypatch: pytest.MonkeyPatch, order: dict[str, Any]
    ) -> None:
        table = FakeTable(order)
        _patch_table(monkeypatch, table)

        result = json.loads(refund.initiate_refund("ORD-1", 2500.0, reason="damaged"))
        assert result["status"] == "initiated"
        assert result["refund_id"].startswith("RF-")
        assert result["estimated_days"] == refund.ESTIMATED_SETTLEMENT_DAYS
        assert len(table.updates) == 1

    def test_the_write_is_guarded_against_a_double_refund(
        self, monkeypatch: pytest.MonkeyPatch, order: dict[str, Any]
    ) -> None:
        table = FakeTable(order)
        _patch_table(monkeypatch, table)
        refund.initiate_refund("ORD-1", 100.0)

        # The condition is what makes two concurrent requests safe. Without
        # it, both would read "delivered" and both would write a refund.
        condition = table.updates[0]["ConditionExpression"]
        assert "attribute_exists(order_id)" in condition
        assert "<> :refunded" in condition

    def test_already_refunded_is_reported_not_retried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from botocore.exceptions import ClientError

        already = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "no"}},
            "UpdateItem",
        )
        table = FakeTable(
            {"order_id": "ORD-1", "total_inr": 2500, "refund_id": "RF-EXISTING"},
            update_error=already,
        )
        _patch_table(monkeypatch, table)

        result = json.loads(refund.initiate_refund("ORD-1", 100.0))
        assert result["error"] == "order has already been refunded"
        assert result["existing_refund_id"] == "RF-EXISTING"

    def test_unconfigured_table_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(refund, "ORDERS_TABLE", "")
        assert "not configured" in json.loads(refund.initiate_refund("ORD-1", 1.0))["error"]


class TestPriceCompare:
    def test_stale_pricing_is_flagged_and_not_summarised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            price_compare,
            "_load_feed",
            lambda: {"SKU-1": {"captured_at": "2020-01-01", "prices": {"acme": 100}}},
        )
        result = json.loads(price_compare.compare_price("SKU-1", 120.0))
        assert result["stale"] is True
        # A stale price must not be handed to the model as a conclusion.
        assert "summary" not in result
        assert "do not quote" in result["note"]

    def test_missing_sku_returns_no_comparisons(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_compare, "_load_feed", dict)
        result = json.loads(price_compare.compare_price("SKU-X", 10.0))
        assert result["comparisons"] == []

    def test_unparseable_timestamp_counts_as_stale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            price_compare,
            "_load_feed",
            lambda: {"SKU-1": {"captured_at": "not-a-date", "prices": {"acme": 100}}},
        )
        assert json.loads(price_compare.compare_price("SKU-1", 120.0))["stale"] is True
