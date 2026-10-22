
import re
from dataclasses import dataclass


@dataclass
class FilterResult:
    is_valid: bool
    reason: str


GREETING_ONLY = {
    "hi",
    "hello",
    "hey",
    "hi there",
    "hello there",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
}


PROMOTIONAL_PHRASES = [
    "buy now",
    "buy our product",
    "special discount",
    "limited time offer",
    "click here to win",
    "subscribe now",
    "earn money fast",
    "sponsored message",
    "exclusive offer",
    "act now",
    "free trial offer",
    "lowest price",
    "huge discount",
    "flash sale",
    "promotional offer",
    "shop now",
    "order today",
    "limited offer",
]


PROMOTIONAL_PATTERNS = [
    r"\b\d{1,3}%\s*off\b",
    r"\bdiscounts?\s+available\b",
    r"\b(save|saving)\s+\d{1,3}%\b",
    r"\b(buy|purchase)\s+(our|this|my)\s+product\b",
    r"\b(buy|order|shop)\s+today\b",
]


def filter_message(message: str) -> FilterResult:
    """Filter empty messages, standalone greetings, and promotions."""

    if not isinstance(message, str) or not message.strip():
        return FilterResult(False, "Empty or invalid message")

    # Normalize whitespace and punctuation for greeting comparison.
    normalized = re.sub(r"[^\w\s]", "", message.lower())
    normalized = " ".join(normalized.split())

    if normalized in GREETING_ONLY:
        return FilterResult(False, "Standalone greeting")

    # Reject greeting-only pleasantries (not just single-word greetings),
    # while still allowing greetings followed by a real support request.
    greeting_pleasantries = [
        r"^(hi|hello|hey)( there)?( team| everyone)?(,)? (hope you are having|hope you have|i hope you have) (a )?(nice|great|good|wonderful) (day|week|weekend)[.! ]*$",
        r"^(good morning|good afternoon|good evening)[,! ]+(hope you are doing well|hope all is well)[.! ]*$",
        r"^(how are you|how is it going)[?! .]*$",
    ]
    if any(re.match(pattern, normalized) for pattern in greeting_pleasantries):
        return FilterResult(False, "Greeting or social pleasantry without customer feedback")

    lower_message = " ".join(message.lower().split())

    # Reject common promotional phrases.
    if any(
        phrase in lower_message
        for phrase in PROMOTIONAL_PHRASES
    ):
        return FilterResult(
            False,
            "Promotional or spam message",
        )

    # Reject messages matching common promotional patterns.
    if any(
        re.search(pattern, lower_message)
        for pattern in PROMOTIONAL_PATTERNS
    ):
        return FilterResult(
            False,
            "Promotional or spam message",
        )

    # Greetings attached to genuine support requests are allowed.
    return FilterResult(True, "Valid customer message")
