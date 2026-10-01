from odoo import fields, models


class ReviewWizard(models.TransientModel):
    _name = "trustgate.review.wizard"
    _description = "Payment Review Decision"

    request_id = fields.Many2one("trustgate.payment.request", required=True, readonly=True)
    note = fields.Text(required=True, string="Rationale")

    def action_approve(self):
        self.ensure_one()
        self.request_id.action_approve(self.note)
        return {"type": "ir.actions.act_window_close"}

    def action_reject(self):
        self.ensure_one()
        self.request_id.action_reject(self.note)
        return {"type": "ir.actions.act_window_close"}
