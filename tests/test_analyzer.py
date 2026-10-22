
from app.services.analyzer import (
    analyze_message,
    classify_intent,
    detect_priority,
    analyze_sentiment,
    extract_product_feature,
)


def test_checkout_crash():
    message = "The checkout page crashes every time. Please fix this ASAP!"
    result = analyze_message(message)

    assert result["category"] == "Bug Report"
    assert result["priority"] == "Urgent"
    assert result["sentiment"] == "Negative"
    assert result["product_feature"] == "Checkout"
    assert result["suggested_reply"]


def test_dark_mode_request():
    message = "Please add dark mode to the mobile app."
    result = analyze_message(message)

    assert result["category"] == "Feature Request"
    assert result["product_feature"] == "Dark Mode"
    assert result["suggested_reply"]


def test_billing_classification():
    assert classify_intent("I was charged twice for my subscription.") == (
        "Billing Issue"
    )


def test_priority_is_not_the_same_as_sentiment():
    message = "The app is slow, but I can still use it."
    assert detect_priority(message) == "Low"


def test_neutral_message():
    assert analyze_sentiment("What are your business hours?") == "Neutral"


def test_unknown_feature():
    assert extract_product_feature("I have a question about something.") == (
        "Not identified"
    )


def test_assessment_payment_page_crash_is_bug_urgent_negative():
    message = "The payment page crashes every time I click 'Checkout' on Chrome. Please fix this ASAP!"
    result = analyze_message(message)
    assert result["category"] == "Bug Report"
    assert result["priority"] == "Urgent"
    assert result["sentiment"] == "Negative"
    assert result["product_feature"] == "Checkout"


def test_assessment_dark_mode_request_is_feature_request_medium_positive():
    message = "Hi team, it would be awesome if you could add a dark mode to the mobile app."
    result = analyze_message(message)
    assert result["category"] == "Feature Request"
    assert result["priority"] == "Medium"
    assert result["sentiment"] == "Positive"
    assert result["product_feature"] == "Dark Mode"
