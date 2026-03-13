import unittest
from unittest.mock import Mock, patch

from src.models import CartItem, Order
from src.pricing import PricingService, PricingError
from src.checkout import CheckoutService, ChargeResult


class TestCheckoutService(unittest.TestCase):
    def setUp(self):
        self.payments = Mock()
        self.email = Mock()
        self.fraud = Mock()
        self.repo = Mock()
        self.pricing = Mock(spec=PricingService)
        self.service = CheckoutService(
            payments=self.payments,
            email=self.email,
            fraud=self.fraud,
            repo=self.repo,
            pricing=self.pricing,
        )

    def test_checkout_returns_invalid_user_for_blank_user_id(self):
        result = self.service.checkout(
            user_id="   ",
            items=[CartItem("A", 1000, 1)],
            payment_token="tok_1",
            country="CL",
        )
        self.assertEqual("INVALID_USER", result)
        self.pricing.total_cents.assert_not_called()
        self.fraud.score.assert_not_called()
        self.payments.charge.assert_not_called()
        self.repo.save.assert_not_called()
        self.email.send_receipt.assert_not_called()

    def test_checkout_returns_invalid_cart_when_pricing_raises(self):
        self.pricing.total_cents.side_effect = PricingError("invalid coupon")
        result = self.service.checkout(
            user_id="u1",
            items=[CartItem("A", 1000, 1)],
            payment_token="tok_1",
            country="CL",
            coupon_code="BAD",
        )
        self.assertEqual("INVALID_CART:invalid coupon", result)
        self.fraud.score.assert_not_called()
        self.payments.charge.assert_not_called()
        self.repo.save.assert_not_called()
        self.email.send_receipt.assert_not_called()

    def test_checkout_rejects_fraud(self):
        self.pricing.total_cents.return_value = 10000
        self.fraud.score.return_value = 80
        result = self.service.checkout(
            user_id="u1",
            items=[CartItem("A", 1000, 1)],
            payment_token="tok_1",
            country="CL",
        )
        self.assertEqual("REJECTED_FRAUD", result)
        self.payments.charge.assert_not_called()
        self.repo.save.assert_not_called()
        self.email.send_receipt.assert_not_called()

    def test_checkout_returns_payment_failed_when_gateway_fails(self):
        self.pricing.total_cents.return_value = 12000
        self.fraud.score.return_value = 20
        self.payments.charge.return_value = ChargeResult(ok=False, reason="DECLINED")
        result = self.service.checkout(
            user_id="u1",
            items=[CartItem("A", 1000, 1)],
            payment_token="tok_1",
            country="CL",
        )
        self.assertEqual("PAYMENT_FAILED:DECLINED", result)
        self.repo.save.assert_not_called()
        self.email.send_receipt.assert_not_called()

    def test_checkout_ok_saves_order_and_sends_receipt_with_known_charge_id(self):
        self.pricing.total_cents.return_value = 15000
        self.fraud.score.return_value = 10
        self.payments.charge.return_value = ChargeResult(ok=True, charge_id="ch_123")
        with patch("src.checkout.uuid.uuid4", return_value="fixed-order-id"):
            result = self.service.checkout(
                user_id="user-1",
                items=[CartItem("A", 5000, 3)],
                payment_token="tok_1",
                country=" cl ",
                coupon_code="SAVE10",
            )
        self.assertEqual("OK:fixed-order-id", result)
        self.payments.charge.assert_called_once_with(
            user_id="user-1", amount_cents=15000, payment_token="tok_1"
        )
        self.repo.save.assert_called_once()
        saved_order = self.repo.save.call_args[0][0]
        self.assertIsInstance(saved_order, Order)
        self.assertEqual("fixed-order-id", saved_order.order_id)
        self.assertEqual("user-1", saved_order.user_id)
        self.assertEqual(15000, saved_order.total_cents)
        self.assertEqual("ch_123", saved_order.payment_charge_id)
        self.assertEqual("SAVE10", saved_order.coupon_code)
        self.assertEqual("CL", saved_order.country)
        self.email.send_receipt.assert_called_once_with("user-1", "fixed-order-id", 15000)

    def test_checkout_ok_uses_unknown_when_charge_id_is_missing(self):
        self.pricing.total_cents.return_value = 7000
        self.fraud.score.return_value = 0
        self.payments.charge.return_value = ChargeResult(ok=True, charge_id=None)
        with patch("src.checkout.uuid.uuid4", return_value="order-2"):
            result = self.service.checkout(
                user_id="user-2",
                items=[CartItem("A", 7000, 1)],
                payment_token="tok_2",
                country="US",
            )
        self.assertEqual("OK:order-2", result)
        saved_order = self.repo.save.call_args[0][0]
        self.assertEqual("UNKNOWN", saved_order.payment_charge_id)
