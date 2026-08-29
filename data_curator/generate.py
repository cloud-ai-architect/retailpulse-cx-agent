"""Synthetic retail data generator for RetailPulse demos.

Generates:
- Product catalog (master.json)
- Customer profiles
- Order history
- FAQ documents
- Return policies

Usage:
    python data_curator/generate.py [--output-dir ./output] [--count 100]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


CATEGORIES = [
    ("apparel", "men", "shirts"),
    ("apparel", "men", "pants"),
    ("apparel", "women", "dresses"),
    ("apparel", "women", "shirts"),
    ("electronics", "audio", "headphones"),
    ("electronics", "computing", "laptops"),
    ("electronics", "phones", "smartphones"),
    ("home", "kitchen", "appliances"),
    ("home", "decor", "lighting"),
    ("beauty", "skincare", "moisturizer"),
    ("beauty", "makeup", "lipstick"),
    ("sports", "fitness", "yoga"),
]

BRANDS = ["Northwood", "Acme", "Globex", "Initech", "Hooli", "Vandelay", "Stark", "Wayne"]

ADJECTIVES = ["Classic", "Premium", "Pro", "Ultra", "Essential", "Smart", "Eco", "Deluxe"]


def make_product(i: int) -> dict:
    cat, subcat, item_type = random.choice(CATEGORIES)
    brand = random.choice(BRANDS)
    adj = random.choice(ADJECTIVES)
    price = round(random.uniform(299, 29999), 2)
    return {
        "sku": f"SKU-{i:05d}",
        "name": f"{brand} {adj} {item_type.title()} {i}",
        "category": f"{cat}/{subcat}/{item_type}",
        "brand": brand,
        "price_inr": price,
        "stock": random.randint(0, 200),
        "sizes": random.sample(["XS", "S", "M", "L", "XL", "XXL"], k=random.randint(2, 5)) if cat == "apparel" else None,
        "description": (
            f"High-quality {item_type} from {brand}. Perfect for everyday use. "
            f"{adj} design with attention to detail. Limited stock available."
        ),
    }


def make_customer(i: int) -> dict:
    first_names = ["Aarav", "Diya", "Vihaan", "Ananya", "Reyansh", "Saanvi", "Ayaan", "Aadhya", "Krishna", "Ishaan"]
    last_names = ["Sharma", "Verma", "Patel", "Kumar", "Singh", "Gupta", "Iyer", "Reddy", "Nair", "Joshi"]
    return {
        "customer_id": f"CUST-{i:06d}",
        "name": f"{random.choice(first_names)} {random.choice(last_names)}",
        "email": f"customer{i}@example.com",
        "phone": f"+91{random.randint(7000000000, 9999999999)}",
        "language": "en-IN",
    }


def make_order(customer_id: str, products: list[dict], i: int) -> dict:
    num_items = random.randint(1, 4)
    items = []
    for _ in range(num_items):
        p = random.choice(products)
        items.append({"sku": p["sku"], "name": p["name"], "qty": random.randint(1, 3), "price_inr": p["price_inr"]})
    total = sum(it["qty"] * it["price_inr"] for it in items)
    days_ago = random.randint(1, 90)
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "order_id": f"ORD-{i:06d}",
        "customer_id": customer_id,
        "items": items,
        "total_inr": total,
        "status": random.choice(["delivered", "delivered", "shipped", "pending"]),
        "delivery_tracking": f"3PL{random.randint(100000, 999999)}",
        "created_at": created.isoformat(),
        "delivered_at": (created + timedelta(days=3)).isoformat() if random.random() > 0.3 else None,
    }


FAQ_DOCS = [
    {
        "title": "How do I track my order?",
        "content": "You can track your order using the tracking number sent to your email. Visit our website and enter your order ID to see real-time updates. Tracking usually activates within 24 hours of shipment.",
        "category": "shipping",
    },
    {
        "title": "What payment methods do you accept?",
        "content": "We accept all major credit cards, debit cards, UPI, net banking, and popular wallets including Paytm, PhonePe, and Google Pay. COD available on orders under ₹5000.",
        "category": "payment",
    },
    {
        "title": "Do you offer international shipping?",
        "content": "Yes! We ship to over 50 countries. International shipping rates are calculated at checkout based on destination and weight. Delivery typically takes 7-14 business days.",
        "category": "shipping",
    },
    {
        "title": "How can I change or cancel my order?",
        "content": "You can modify or cancel your order within 2 hours of placement. After that, the order enters fulfillment and cannot be changed. For cancellations, contact our support team.",
        "category": "orders",
    },
    {
        "title": "Do you have a loyalty program?",
        "content": "Yes! Join our loyalty program to earn points on every purchase. 1 point per ₹100 spent. Redeem points for discounts on future orders. Sign up free during checkout.",
        "category": "account",
    },
]

POLICY_DOCS = [
    {
        "title": "Return Policy",
        "content": (
            "Most items can be returned within 30 days of delivery for a full refund. "
            "Items must be unused, in original packaging, with all tags attached. "
            "Final sale items, personalized items, and perishable goods cannot be returned. "
            "Electronics have a 15-day return window. Defective items are always eligible for return."
        ),
        "category": "returns",
    },
    {
        "title": "Refund Policy",
        "content": (
            "Refunds are processed within 5-7 business days after we receive your return. "
            "The refund will be issued to the original payment method. "
            "For UPI/wallet payments, refunds typically appear within 24 hours. "
            "Shipping costs are non-refundable unless the item was defective."
        ),
        "category": "refunds",
    },
    {
        "title": "Shipping Policy",
        "content": (
            "Standard shipping (3-5 business days) is free on orders over ₹500. "
            "Express shipping (1-2 business days) is available for ₹99. "
            "Same-day delivery is available in major metros for ₹199. "
            "International shipping takes 7-14 business days."
        ),
        "category": "shipping",
    },
]


def generate_catalog(count: int = 100) -> list[dict]:
    return [make_product(i) for i in range(1, count + 1)]


def generate_customers(count: int = 50) -> list[dict]:
    return [make_customer(i) for i in range(1, count + 1)]


def generate_orders(customers: list[dict], products: list[dict], per_customer: int = 3) -> list[dict]:
    orders = []
    i = 1
    for c in customers:
        for _ in range(per_customer):
            orders.append(make_order(c["customer_id"], products, i))
            i += 1
    return orders


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic retail data")
    parser.add_argument("--output-dir", default="./output", help="Where to write the data")
    parser.add_argument("--count", type=int, default=100, help="Number of products")
    parser.add_argument("--customers", type=int, default=50, help="Number of customers")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} products...")
    catalog = generate_catalog(args.count)
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"  -> {out / 'catalog.json'} ({len(catalog)} items)")

    print(f"Generating {args.customers} customers...")
    customers = generate_customers(args.customers)
    (out / "customers.json").write_text(json.dumps(customers, indent=2))
    print(f"  -> {out / 'customers.json'} ({len(customers)} customers)")

    print("Generating orders...")
    orders = generate_orders(customers, catalog, per_customer=3)
    (out / "orders.jsonl").write_text("\n".join(json.dumps(o) for o in orders))
    print(f"  -> {out / 'orders.jsonl'} ({len(orders)} orders)")

    print("Generating FAQ + policy docs...")
    (out / "faq.json").write_text(json.dumps(FAQ_DOCS, indent=2))
    (out / "policies.json").write_text(json.dumps(POLICY_DOCS, indent=2))
    print(f"  -> faq.json ({len(FAQ_DOCS)}), policies.json ({len(POLICY_DOCS)})")

    print("\nDone. Upload to S3:")
    print(f"  aws s3 sync {out}/ s3://retailpulse-dev-catalog/ --region ap-south-1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
