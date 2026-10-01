from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestPaymentRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(cls.env, login="trust_operator", groups="trustgate.group_operator")
        cls.reviewer = new_test_user(cls.env, login="trust_reviewer", groups="trustgate.group_reviewer")
        cls.supplier = cls.env["res.partner"].create({"name": "Example Supplier"})
        cls.bank = cls.env["res.partner.bank"].create({
            "partner_id": cls.supplier.id, "account_number": "BE68539007547034",
        })
        cls.Request = cls.env["trustgate.payment.request"]

    def request(self, amount=20000, user=None):
        return self.Request.with_user(user or self.operator).create({
            "name": "Invoice review", "partner_id": self.supplier.id,
            "bank_id": self.bank.id, "amount": amount,
        })

    def pending(self, user=None):
        request = self.request(user=user)
        request.action_submit()
        self.assertEqual(request.state, "review")
        return request

    def test_high_risk_requires_review(self):
        request = self.pending()
        self.assertGreaterEqual(request.risk_score, 50)
        self.assertEqual(request.requested_by, self.operator)
        self.assertEqual(request.bank_last_four, "7034")
        self.assertTrue(request.submitted_at)

    def test_independent_review(self):
        request = self.pending()
        request.with_user(self.reviewer).action_approve("Confirmed supplier details by phone.")
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.reviewed_by, self.reviewer)
        self.assertTrue(request.message_ids)

    def test_requester_cannot_review(self):
        request = self.pending(user=self.reviewer)
        with self.assertRaises(AccessError):
            request.action_approve("Self approval")

    def test_operator_cannot_review(self):
        request = self.pending()
        with self.assertRaises(AccessError):
            request.action_approve("No reviewer role")

    def test_terminal_decision(self):
        request = self.pending().with_user(self.reviewer)
        request.action_reject("Unable to verify beneficiary.")
        with self.assertRaises(UserError):
            request.action_approve("Retry")

    def test_required_rationale(self):
        request = self.pending().with_user(self.reviewer)
        with self.assertRaises(ValidationError):
            request.action_approve(" ")

    def test_direct_state_and_identity_injection(self):
        for extra in ({"state": "approved"}, {"requested_by": self.reviewer.id}, {"risk_score": 0}):
            with self.assertRaises(AccessError):
                self.Request.with_user(self.operator).create({
                    "name": "Forged", "partner_id": self.supplier.id,
                    "bank_id": self.bank.id, "amount": 10, **extra,
                })
        request = self.request()
        with self.assertRaises(AccessError):
            request.write({"state": "approved"})

    def test_submitted_values_are_frozen(self):
        request = self.pending()
        with self.assertRaises(AccessError):
            request.write({"amount": 1})
        with self.assertRaises(AccessError):
            request.unlink()

    def test_bank_owner(self):
        other = self.env["res.partner"].create({"name": "Other supplier"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Request.with_user(self.operator).create({
                "name": "Wrong beneficiary", "partner_id": other.id,
                "bank_id": self.bank.id, "amount": 100,
            })

    def test_changed_bank_cannot_be_approved(self):
        request = self.pending()
        self.bank.account_number = "BE71096123456769"
        with self.assertRaises(UserError):
            request.with_user(self.reviewer).action_approve("Checked earlier")
        request.with_user(self.reviewer).action_reject("Bank details changed")

    def test_company_isolation(self):
        company = self.env["res.company"].create({"name": "Other company"})
        self.operator.company_ids = [Command.link(company.id)]
        request = self.Request.with_user(self.operator).with_context(allowed_company_ids=[company.id]).create({
            "name": "Other company request", "company_id": company.id,
            "partner_id": self.supplier.id, "bank_id": self.bank.id, "amount": 20000,
        })
        with self.assertRaises(AccessError):
            request.with_user(self.reviewer).read(["name"])

    def test_low_risk_auto_approval(self):
        # A fresh bank scores 30 and a new supplier 15 during business hours.
        now = datetime(2026, 9, 28, 10, 0, 0)
        request = self.request(amount=100)
        with patch("odoo.addons.trustgate.models.payment_request.fields.Datetime.now", return_value=now):
            request.action_submit()
        self.assertEqual(request.risk_score, 45)
        self.assertEqual(request.state, "approved")
