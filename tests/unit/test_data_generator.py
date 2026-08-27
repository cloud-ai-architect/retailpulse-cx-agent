"""Tests for the synthetic data generator."""

from __future__ import annotations

import json

from data_curator.generate import (
    generate_catalog,
    generate_customers,
    generate_orders,
    make_product,
    make_customer,
    make_order,
)


class TestCatalog:
    def test_generate_catalog_size(self):
        catalog = generate_catalog(50)
        assert len(catalog) == 50

    def test_product_has_required_fields(self):
        p = make_product(1)
        for field in ("sku", "name", "category", "brand", "price_inr", "stock", "description"):
            assert field in p, f"Missing {field}"
        assert p["sku"] == "SKU-00001"
        assert p["price_inr"] > 0
        assert p["stock"] >= 0


class TestCustomers:
    def test_generate_customers_size(self):
        customers = generate_customers(20)
        assert len(customers) == 20

    def test_customer_has_required_fields(self):
        c = make_customer(1)
        for field in ("customer_id", "name", "email", "phone", "language"):
            assert field in c
        assert c["customer_id"] == "CUST-000001"
        assert c["language"] == "en-IN"


class TestOrders:
    def test_orders_have_required_fields(self):
        catalog = generate_catalog(5)
        customers = generate_customers(3)
        orders = generate_orders(customers, catalog, per_customer=2)
        assert len(orders) == 6
        for o in orders:
            for field in ("order_id", "customer_id", "items", "total_inr", "status", "created_at"):
                assert field in o
            assert o["total_inr"] > 0
            assert len(o["items"]) > 0
