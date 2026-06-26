"""Rule-based ticket classifier.

The service must classify a single CRM ticket into:

    case_type   ∈ { wrong_transfer, payment_failed, refund_request,
                    phishing_or_social_engineering, other }
    severity    ∈ { low, medium, high, critical }
    department  ∈ { customer_support, dispute_resolution,
                    payments_ops, fraud_risk }
    agent_summary  : one neutral sentence
    human_review_required : bool
    confidence   : float in [0, 1]

Design notes
------------
* Phishing is checked **first**. If the message asks for / mentions PIN, OTP,
  password, or a suspicious contact pattern, the case is ``phishing_or_social_
  engineering`` regardless of what other keywords appear. This guarantees that
  a scam message is never miscategorised as a payment or refund issue.

* For the remaining four categories we count keyword hits (English +
  Bangla transliteration, since ``locale`` may be ``bn`` or ``mixed``).
  The category with the highest hit count wins. Ties break in the
  declared priority order below (most customer-impact first).

* Confidence is a function of keyword density. With zero hits it is
  ``0.5`` (fallback) and it climbs by ``0.1`` per hit, capped at ``0.95``.

* ``agent_summary`` is templated. Templates use only neutral verbs
  (reports, requests, mentions, ...) — no "share", "send me", "provide",
  "tell me your" — and the output is run through ``safety.scrub`` so
  even an accidental regression cannot leak a forbidden term.

* Amount extraction: regex finds the largest number in the message;
  if any of ``taka``, ``bdt``, ``tk``, ``৳`` is also present, the
  summary mentions ``<n> BDT``. Otherwise the amount is omitted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import safety


# --- Keyword sets ----------------------------------------------------------
# Order matters: phishing is checked first, then the rest in declared priority.

_PHISHING_KEYWORDS: Tuple[str, ...] = (
    # English
    "otp", "one time password", "one-time password",
    "verification code", "security code",
    "share your pin", "send your pin", "give me your pin", "ask for pin",
    "share your otp", "send your otp", "give me your otp", "ask for otp",
    "share your password", "send your password",
    "share your cvv", "send your cvv",
    "share your card", "send your card number",
    "share card number", "send card number",
    "asked for my otp", "asked for my pin", "asked for otp", "asked for pin",
    "calling asking", "called asking", "call asking",
    "asking for otp", "asking for pin", "asking for password",
    "asking my otp", "asking my pin", "asking my password",
    "is that bkash", "is that nagad", "fake bkash", "fake nagad",
    "phishing", "scam call", "scam message", "fraud call",
    "fraudster", "impersonat", "pretending to be",
    # Bangla transliteration
    "ওটিপি", "পিন", "পাসওয়ার্ড", "পাসওয়ার্ড দিন", "ভেরিফিকেশন কোড",
    "পিন দিন", "ওটিপি দিন", "আমাকে পিন", "আমাকে ওটিপি",
    "প্রতারণা", "স্ক্যাম",
)

_WRONG_TRANSFER_KEYWORDS: Tuple[str, ...] = (
    # English
    "wrong number", "wrong account", "wrong person", "wrong recipient",
    "sent to wrong", "sent money to wrong", "transferred to wrong",
    "mistakenly sent", "by mistake", "sent it to wrong",
    "accidentally sent", "wrongly sent", "sent to the wrong",
    "transferred by mistake", "paid the wrong",
    # Bangla
    "ভুল নম্বরে", "ভুল নাম্বারে", "ভুল একাউন্টে", "ভুল ব্যক্তিকে",
    "ভুল ব্যক্তির কাছে", "ভুল করে পাঠিয়ে", "ভুল করে টাকা",
    "ভুল রিসিভার", "ভুলে পাঠিয়ে",
)

_PAYMENT_FAILED_KEYWORDS: Tuple[str, ...] = (
    # English
    "payment failed", "transaction failed", "failed transaction",
    "failed but balance", "balance deducted", "money deducted",
    "amount deducted", "deducted from account", "deducted but not",
    "didn't receive", "did not receive", "not received",
    "payment pending", "transaction pending", "pending transaction",
    "payment didn't go through", "transaction didn't go through",
    "didn't go through", "did not go through", "not go through",
    "no go through", "couldn't go through", "could not go through",
    "money not received", "amount not received", "recipient didn't get",
    "stuck in pending", "reversed but not",
    # Bangla
    "পেমেন্ট ফেইল", "পেমেন্ট ব্যর্থ", "ট্রানজেকশন ফেইল",
    "টাকা কেটে নিয়েছে", "ব্যালেন্স কেটে", "টাকা কাটা হয়েছে",
    "টাকা কাটা হয়ে গেছে", "পেমেন্ট আটকে", "পেন্ডিং আছে",
    "পেমেন্ট হয়নি", "টাকা পাইনি", "টাকা পাইনি এখনো",
)

_REFUND_KEYWORDS: Tuple[str, ...] = (
    # English
    "refund", "refund my", "money back", "return my money",
    "cancel my transaction", "cancel my payment", "reverse the",
    "i changed my mind", "changed my mind", "want my money back",
    "please refund", "request refund", "refund request",
    "revert the transaction", "revert my payment", "chargeback",
    # Bangla
    "রিফান্ড", "টাকা ফেরত", "টাকা ফেরত দিন", "ফেরত চাই",
    "ফেরত দিতে হবে", "টাকা ফিরিয়ে", "ক্যান্সেল করুন",
    "পেমেন্ট ক্যান্সেল",
)


# --- Severity / department helpers -----------------------------------------

# Refund severity escalators.
_REFUND_ESCALATE_TO_HIGH = (
    "double charged", "charged twice", "duplicate charge",
    "fraudulent charge", "unauthorized", "unauthorised",
    "10000", "20000", "30000", "40000", "50000",
    "10,000", "20,000", "30,000", "40,000", "50,000",
)


# --- Number / amount extraction --------------------------------------------

_NUMBER_RE = re.compile(r"\b\d[\d,\.]*\b")
_CURRENCY_HINTS = ("taka", "bdt", "tk", "৳")


def _extract_amount(message: str) -> Optional[str]:
    """Return the largest number in ``message`` suffixed with ``BDT`` if a
    currency keyword is present, otherwise ``None``.
    """
    matches = _NUMBER_RE.findall(message)
    if not matches:
        return None
    # Pick the largest numeric value (ignore commas / dots).
    def _to_num(s: str) -> float:
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return 0.0

    biggest = max(matches, key=_to_num)
    # Avoid leaking phone numbers as amounts: only treat as amount when the
    # number is reasonable (≤ 10 digits and not 11+ digit phone numbers).
    digits = biggest.replace(",", "").replace(".", "")
    if len(digits) > 9:
        return None
    if any(h in message.lower() for h in _CURRENCY_HINTS):
        return f"{biggest} BDT"
    return None


# --- Counting ---------------------------------------------------------------

def _count_hits(message_lower: str, keywords: Tuple[str, ...]) -> int:
    """Return how many of the given keywords appear in ``message_lower``."""
    hits = 0
    for kw in keywords:
        if kw in message_lower:
            hits += 1
    return hits


def _matches_phishing(message_lower: str) -> bool:
    if _count_hits(message_lower, _PHISHING_KEYWORDS) > 0:
        return True
    # Heuristic: "asked for OTP / PIN / password" pattern is extremely
    # common in scam reports. Catch the bare noun forms in scam context.
    danger_terms = ("otp", "pin", "password", "cvv", "verification code")
    ask_verbs = (
        "ask", "asks", "asked", "asking",
        "want", "wants", "wanted",
        "need", "needs", "needed",
        "request", "requests", "requested",
        "tell me", "give me", "share", "send",
    )
    has_danger = any(t in message_lower for t in danger_terms)
    has_ask = any(v in message_lower for v in ask_verbs)
    return has_danger and has_ask


# --- Summary templates ------------------------------------------------------

def _summary_phishing(amount: Optional[str]) -> str:
    base = "Customer reports receiving a suspicious contact requesting sensitive verification information"
    if amount:
        base += f" related to a {amount} transaction"
    return base + "."


def _summary_wrong_transfer(amount: Optional[str]) -> str:
    if amount:
        return (
            f"Customer reports sending {amount} to a wrong number and requests recovery."
        )
    return "Customer reports sending money to a wrong recipient and requests recovery."


def _summary_payment_failed(amount: Optional[str]) -> str:
    if amount:
        return (
            f"Customer reports a failed transaction of {amount} with possible balance deduction."
        )
    return "Customer reports a failed transaction with possible balance deduction."


def _summary_refund(amount: Optional[str]) -> str:
    if amount:
        return f"Customer requests a refund for a recent {amount} transaction."
    return "Customer requests a refund for a recent transaction."


def _summary_other() -> str:
    return "Customer reports an issue and is seeking assistance."


# --- Public classification entry point --------------------------------------

@dataclass(frozen=True)
class Classification:
    case_type: str
    severity: str
    department: str
    agent_summary: str
    human_review_required: bool
    confidence: float


def classify(message: str) -> Classification:
    """Classify a free-text customer message into the spec's fields."""
    msg = message or ""
    msg_lower = msg.lower()

    # 1) Phishing is always checked first and is the only category that
    #    forces severity=critical and department=fraud_risk.
    if _matches_phishing(msg_lower):
        summary = safety.scrub(_summary_phishing(_extract_amount(msg)))
        return Classification(
            case_type="phishing_or_social_engineering",
            severity="critical",
            department="fraud_risk",
            agent_summary=summary,
            human_review_required=True,
            confidence=0.95,
        )

    # 2) Score the remaining categories.
    hits_wrong = _count_hits(msg_lower, _WRONG_TRANSFER_KEYWORDS)
    hits_pay = _count_hits(msg_lower, _PAYMENT_FAILED_KEYWORDS)
    hits_refund = _count_hits(msg_lower, _REFUND_KEYWORDS)

    # 3) Pick the winner (priority order on ties: wrong > pay > refund).
    best_category = "other"
    best_hits = 0
    if hits_wrong > best_hits:
        best_category = "wrong_transfer"
        best_hits = hits_wrong
    if hits_pay > best_hits:
        best_category = "payment_failed"
        best_hits = hits_pay
    if hits_refund > best_hits and hits_refund >= hits_pay and hits_refund >= hits_wrong:
        # only let refund win on ties if it's not behind
        best_category = "refund_request"
        best_hits = hits_refund
    # If nothing matched, fall back to "other" with low confidence.
    if best_hits == 0:
        return Classification(
            case_type="other",
            severity="low",
            department="customer_support",
            agent_summary=safety.scrub(_summary_other()),
            human_review_required=False,
            confidence=0.5,
        )

    # 4) Build the result based on the winning category.
    amount = _extract_amount(msg)

    if best_category == "wrong_transfer":
        return Classification(
            case_type="wrong_transfer",
            severity="high",
            department="dispute_resolution",
            agent_summary=safety.scrub(_summary_wrong_transfer(amount)),
            human_review_required=False,
            confidence=_confidence(best_hits),
        )

    if best_category == "payment_failed":
        return Classification(
            case_type="payment_failed",
            severity="high",
            department="payments_ops",
            agent_summary=safety.scrub(_summary_payment_failed(amount)),
            human_review_required=False,
            confidence=_confidence(best_hits),
        )

    # refund_request — severity may escalate.
    refund_severity = "low"
    if any(t in msg_lower for t in _REFUND_ESCALATE_TO_HIGH):
        refund_severity = "high"
    refund_dept = "dispute_resolution" if refund_severity == "high" else "customer_support"
    return Classification(
        case_type="refund_request",
        severity=refund_severity,
        department=refund_dept,
        agent_summary=safety.scrub(_summary_refund(amount)),
        human_review_required=False,
        confidence=_confidence(best_hits),
    )


def _confidence(hits: int) -> float:
    """Convert keyword hit count to a 0..1 confidence value."""
    if hits <= 0:
        return 0.5
    val = 0.55 + 0.1 * hits
    return min(val, 0.95)
