"""Safety scrubber for the `agent_summary` field.

The spec's safety rule (auto-fail if violated):
  > The agent_summary field must never ask the customer to share PIN, OTP,
  > password, or full card number.

The summary templates in `classifier.py` are written with neutral verbs, so
under normal circumstances they will never contain those tokens. This module
is a belt-and-braces final pass: it replaces any occurrence of the forbidden
terms with `[redacted]` so the output is provably safe even if a future
template or interpolation step regresses.
"""
import re

# Word-boundary, case-insensitive. Matches:
#   PIN, pin, Pin
#   OTP, otp
#   CVV, cvv
#   password
#   card number, card no, cardnum
_FORBIDDEN = re.compile(
    r"\b("
    r"otps?|pins?|passwords?|cvv|cvv2|card[\s\-]?numbers?|card[\s\-]?nos?|cardnums?"
    r")\b",
    re.IGNORECASE,
)

_REDACTION = "[redacted]"


def scrub(text: str) -> str:
    """Return ``text`` with all forbidden terms replaced by ``[redacted]``.

    The replacement is idempotent: calling ``scrub(scrub(x)) == scrub(x)``.
    """
    return _FORBIDDEN.sub(_REDACTION, text)


def is_safe(text: str) -> bool:
    """Return True iff ``text`` contains no forbidden term."""
    return _FORBIDDEN.search(text) is None
