"""Workflow taxonomy: the statuses for each track and the 'next action' per status.

Three tracks mirror the real departmental flow so the app replaces hand-off emails:

  Promo setup/approval   (PM -> Vendor -> Sales)
  Customer claim         (Sales -> PM -> Accounts), tracked per retailer
  Vendor credit request  (PM -> Vendor -> Accounts)

Each NEXT_ACTION value names the department whose turn it is and what they do, so
whoever opens the promo can see what's outstanding without being emailed.
"""

# ---- Promo setup / approval track -------------------------------------------
PROMO_STATUSES = [
    "Draft",
    "Pending Vendor Approval",
    "Vendor Rejected",
    "Released to Sales",
    "Sent to Customer",
    "Running",
    "Closed",
]
PROMO_NEXT = {
    "Draft": "PM: finalise details, then send to vendor for spend approval",
    "Pending Vendor Approval": "Vendor: approve the planned spend",
    "Vendor Rejected": "PM: revise the promo and re-submit",
    "Released to Sales": "Sales: send the promo to the customer",
    "Sent to Customer": "Promo scheduled — mark Running once it starts",
    "Running": "Promo live — awaiting customer claims after it ends",
    "Closed": "Promo complete",
}

# ---- Customer claim track (per retailer) ------------------------------------
CLAIM_STATUSES = [
    "Awaiting Claim",
    "Received by Sales",
    "Entered by PM",
    "Verified by Accounts",
    "Credited",
]
CLAIM_NEXT = {
    "Awaiting Claim": "Sales: log the customer's claim once received",
    "Received by Sales": "PM: enter actual sales and the claim amount",
    "Entered by PM": "Accounts: verify the claim against actuals",
    "Verified by Accounts": "Accounts: credit the customer",
    "Credited": "Customer credited",
}

# ---- Vendor credit request track --------------------------------------------
VENDOR_STATUSES = [
    "Not Sent",
    "Sent to Vendor",
    "Vendor Approved",
    "Credit Raised",
    "Credit Received",
]
VENDOR_NEXT = {
    "Not Sent": "PM: send the claim to the vendor (cc Accounts)",
    "Sent to Vendor": "Vendor: approve the credit",
    "Vendor Approved": "Accounts: raise the vendor credit request",
    "Credit Raised": "Awaiting vendor credit",
    "Credit Received": "Vendor credit received",
}

# CSS pill colour group per status: started/none(red) | waiting-external(amber) |
# internal-action(blue) | done(green) | neutral(grey)
PILL_GROUP = {
    # promo
    "Draft": "grey", "Pending Vendor Approval": "amber", "Vendor Rejected": "red",
    "Released to Sales": "blue", "Sent to Customer": "amber", "Running": "green",
    "Closed": "grey",
    # claim
    "Awaiting Claim": "red", "Received by Sales": "amber", "Entered by PM": "blue",
    "Verified by Accounts": "blue", "Credited": "green",
    # vendor
    "Not Sent": "red", "Sent to Vendor": "amber", "Vendor Approved": "blue",
    "Credit Raised": "blue", "Credit Received": "green",
}


def context():
    """Bundle for injecting into templates."""
    return {
        "PROMO_STATUSES": PROMO_STATUSES, "PROMO_NEXT": PROMO_NEXT,
        "CLAIM_STATUSES": CLAIM_STATUSES, "CLAIM_NEXT": CLAIM_NEXT,
        "VENDOR_STATUSES": VENDOR_STATUSES, "VENDOR_NEXT": VENDOR_NEXT,
        "PILL_GROUP": PILL_GROUP,
    }
