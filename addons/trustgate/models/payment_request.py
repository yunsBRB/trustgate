import hashlib
from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL


class PaymentRequest(models.Model):
    _name = "trustgate.payment.request"
    _description = "Supplier Payment Review"
    _inherit = ["mail.thread"]
    _check_company_auto = True
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, string="Reference")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    partner_id = fields.Many2one("res.partner", required=True, check_company=True, string="Supplier")
    bank_id = fields.Many2one("res.partner.bank", required=True, check_company=True, string="Bank account")
    amount = fields.Monetary(required=True, tracking=True)
    requested_by = fields.Many2one("res.users", readonly=True, required=True, default=lambda self: self.env.user)
    submitted_at = fields.Datetime(readonly=True)
    reviewed_by = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    review_note = fields.Text(string="Review rationale")
    state = fields.Selection([
        ("draft", "Draft"), ("review", "Pending Review"),
        ("approved", "Approved"), ("rejected", "Rejected"),
    ], required=True, default="draft", readonly=True, tracking=True, index=True)
    risk_score = fields.Integer(readonly=True)
    risk_reasons = fields.Text(readonly=True)
    bank_fingerprint = fields.Char(readonly=True)
    bank_last_four = fields.Char(readonly=True)

    _positive_amount = models.Constraint("CHECK(amount > 0)", "Amount must be positive.")

    @api.constrains("partner_id", "bank_id")
    def _check_bank_owner(self):
        for request in self:
            if request.bank_id.partner_id.commercial_partner_id != request.partner_id.commercial_partner_id:
                raise ValidationError(self.env._("The bank account must belong to the supplier."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if set(vals) - {"name", "company_id", "partner_id", "bank_id", "amount"}:
                raise AccessError(self.env._("Create a draft with payment details only."))
            if vals.get("company_id", self.env.company.id) not in self.env.companies.ids:
                raise AccessError(self.env._("Select an allowed company."))
        return super().create([dict(vals, requested_by=self.env.uid, state="draft") for vals in vals_list])

    def _lock_for_update(self):
        self.check_access("write")
        self.flush_recordset()
        if self.ids:
            self.env.cr.execute(SQL("SELECT id FROM trustgate_payment_request WHERE id IN %s ORDER BY id FOR UPDATE", tuple(self.ids)))
        self.invalidate_recordset()
        self.check_access("write")

    def write(self, vals):
        self._lock_for_update()
        if set(vals) - {"name", "company_id", "partner_id", "bank_id", "amount"}:
            raise AccessError(self.env._("Use the review actions to change a decision."))
        for request in self:
            if request.state != "draft" or request.requested_by != self.env.user:
                raise AccessError(self.env._("Only the requester can edit their draft."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(self.env._("Payment review records cannot be deleted."))

    def _assessment(self, now):
        self.ensure_one()
        account = self.bank_id.sanitized_account_number or ""
        fingerprint = hashlib.sha256(account.encode()).hexdigest()
        # Narrow elevation: aggregate prior decisions, restricted to this company,
        # supplier and currency. Do not return other requests to the caller.
        previous = self.sudo().search([
            ("company_id", "=", self.company_id.id), ("partner_id", "=", self.partner_id.id),
            ("currency_id", "=", self.currency_id.id), ("state", "=", "approved"),
            ("id", "!=", self.id),
        ])
        bank_changed = bool(previous and fingerprint not in previous.mapped("bank_fingerprint"))
        bank_recent = self.bank_id.write_date >= now - timedelta(days=7)
        average = sum(previous.mapped("amount")) / len(previous) if previous else 0
        # The cold-start threshold is EUR 10,000 converted through Odoo rates.
        euro = self.env.ref("base.EUR")
        cold_limit = euro._convert(10000, self.currency_id, self.company_id, now.date())
        large_amount = self.amount > (3 * average if previous else cold_limit)
        local = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Brussels"))
        outside_hours = local.weekday() >= 5 or not 8 <= local.hour < 18
        rules = [
            (bank_changed or bank_recent, 30, self.env._("New or recently edited bank account")),
            (large_amount, 20, self.env._("Amount exceeds the supplier baseline")),
            (outside_hours, 15, self.env._("Outside weekday business hours (Brussels)")),
            (not previous, 15, self.env._("No previously approved request")),
        ]
        return {
            "risk_score": sum(weight for matches, weight, _label in rules if matches),
            "risk_reasons": "\n".join(f"+{weight}: {label}" for matches, weight, label in rules if matches)
                            or self.env._("No risk rules triggered."),
            "bank_fingerprint": fingerprint, "bank_last_four": account[-4:],
        }

    def action_submit(self):
        self._lock_for_update()
        for request in self:
            if request.state != "draft" or request.requested_by != self.env.user:
                raise UserError(self.env._("Only the requester can submit their draft."))
            now = fields.Datetime.now()
            values = request._assessment(now)
            values.update(submitted_at=now, state="review" if values["risk_score"] >= 50 else "approved")
            super(PaymentRequest, request).write(values)
            request.message_post(body=self.env._("Risk assessment completed. Score: %s/100.", values["risk_score"]))
        return True

    def _review(self, decision, note):
        if not self.env.user.has_group("trustgate.group_reviewer"):
            raise AccessError(self.env._("A reviewer must make this decision."))
        self._lock_for_update()
        for request in self:
            if request.state != "review":
                raise UserError(self.env._("This request is not waiting for review."))
            if request.requested_by == self.env.user:
                raise AccessError(self.env._("You cannot review your own request."))
            if not isinstance(note, str) or not note.strip():
                raise ValidationError(self.env._("A review rationale is required."))
            # A changed beneficiary requires a new assessment, never approval of stale details.
            account = request.bank_id.sanitized_account_number or ""
            if decision == "approved" and hashlib.sha256(account.encode()).hexdigest() != request.bank_fingerprint:
                raise UserError(self.env._("The bank account changed. Reject this request and create a new one."))
            super(PaymentRequest, request).write({
                "state": decision, "review_note": note.strip(),
                "reviewed_by": self.env.uid, "reviewed_at": fields.Datetime.now(),
            })
            request.message_post(body=self.env._("Review decision: %(decision)s. %(note)s", decision=decision, note=note.strip()))
        return True

    def action_approve(self, note=None):
        return self._review("approved", note)

    def action_reject(self, note=None):
        return self._review("rejected", note)
