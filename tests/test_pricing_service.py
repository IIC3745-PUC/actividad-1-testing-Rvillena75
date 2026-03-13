import unittest

from src.models import CartItem
from src.pricing import PricingService, PricingError


class TestPricingService(unittest.TestCase):
    def setUp(self):
        self.service = PricingService()

    def test_subtotal_cents_happy_path_and_empty(self):
        items = [
            CartItem(sku="A", unit_price_cents=1000, qty=2),
            CartItem(sku="B", unit_price_cents=500, qty=1),
        ]
        subtotal_with_items = self.service.subtotal_cents(items)
        subtotal_empty = self.service.subtotal_cents([])
        self.assertEqual(2500, subtotal_with_items)
        self.assertEqual(0, subtotal_empty)

    def test_subtotal_cents_raises_when_qty_non_positive(self):
        items = [CartItem(sku="A", unit_price_cents=1000, qty=0)]
        with self.assertRaisesRegex(PricingError, "qty must be > 0"):
            self.service.subtotal_cents(items)

    def test_subtotal_cents_raises_when_negative_unit_price(self):
        items = [CartItem(sku="A", unit_price_cents=-1, qty=1)]
        with self.assertRaisesRegex(PricingError, "unit_price_cents must be >= 0"):
            self.service.subtotal_cents(items)

    def test_apply_coupon_returns_same_subtotal_for_none_empty_or_spaces(self):
        self.assertEqual(10000, self.service.apply_coupon(10000, None))
        self.assertEqual(10000, self.service.apply_coupon(10000, ""))
        self.assertEqual(10000, self.service.apply_coupon(10000, "   "))

    def test_apply_coupon_save10_and_clp2000(self):
        self.assertEqual(9000, self.service.apply_coupon(9999, "save10"))
        self.assertEqual(500, self.service.apply_coupon(2500, " CLP2000 "))
        self.assertEqual(0, self.service.apply_coupon(1500, "CLP2000"))

    def test_apply_coupon_raises_for_invalid_coupon(self):
        with self.assertRaisesRegex(PricingError, "invalid coupon"):
            self.service.apply_coupon(10000, "NOPE")

    def test_tax_cents_for_supported_and_unsupported_countries(self):
        self.assertEqual(1900, self.service.tax_cents(10000, "cl"))
        self.assertEqual(2100, self.service.tax_cents(10000, "EU"))
        self.assertEqual(0, self.service.tax_cents(10000, " us "))

        with self.assertRaisesRegex(PricingError, "unsupported country"):
            self.service.tax_cents(10000, "AR")

    def test_shipping_cents_for_supported_and_unsupported_countries(self):
        self.assertEqual(0, self.service.shipping_cents(20000, "CL"))
        self.assertEqual(2500, self.service.shipping_cents(19999, "cl"))
        self.assertEqual(5000, self.service.shipping_cents(1, "US"))
        self.assertEqual(5000, self.service.shipping_cents(1, "eu"))

        with self.assertRaisesRegex(PricingError, "unsupported country"):
            self.service.shipping_cents(10000, "AR")

    def test_total_cents_end_to_end(self):
        items = [
            CartItem(sku="A", unit_price_cents=10000, qty=2),
            CartItem(sku="B", unit_price_cents=1000, qty=1),
        ]
        total = self.service.total_cents(items, "save10", "cl")
        self.assertEqual(24991, total)
