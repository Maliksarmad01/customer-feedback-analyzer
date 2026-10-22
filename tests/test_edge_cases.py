
from app.services.analyzer import analyze_message


def test_security_breach_is_urgent():
    result = analyze_message(
        "Someone accessed my account without permission."
    )
    assert result["priority"] == "Urgent"


def test_duplicate_payment_is_billing_issue():
    result = analyze_message(
        "I was charged twice for my subscription."
    )
    assert result["category"] == "Billing Issue"


def test_feature_request_is_not_a_bug():
    result = analyze_message(
        "Please add dark mode to the dashboard."
    )
    assert result["category"] == "Feature Request"
    assert result["product_feature"] == "Dark Mode"


def test_positive_feedback_has_positive_sentiment():
    result = analyze_message(
        "I love the app. It is fast and very easy to use."
    )
    assert result["sentiment"] == "Positive"


def test_negative_feedback_has_negative_sentiment():
    result = analyze_message(
        "The application keeps crashing and I am frustrated."
    )
    assert result["sentiment"] == "Negative"


def test_unknown_product_is_not_invented():
    result = analyze_message(
        "Please improve the experience of using this service."
    )
    assert result["product_feature"] == "Not identified"
