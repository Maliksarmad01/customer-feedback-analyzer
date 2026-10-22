
from app.services.filtering import filter_message


def test_standalone_greeting_is_rejected():
    result = filter_message("Hello!")
    assert result.is_valid is False


def test_promotional_message_is_rejected():
    result = filter_message("Buy now! Limited time offer!")
    assert result.is_valid is False


def test_real_bug_report_is_accepted():
    result = filter_message("The checkout page crashes every time.")
    assert result.is_valid is True


def test_greeting_with_real_issue_is_accepted():
    result = filter_message("Hi, the payment page is broken.")
    assert result.is_valid is True


def test_empty_message_is_rejected():
    result = filter_message("")
    assert result.is_valid is False

def test_promotional_message_with_percentage_discount():
    from app.services.filtering import filter_message

    result = filter_message(
        "Buy today and get 50% off on our premium plan!"
    )

    assert result.is_valid is False


def test_legitimate_complaint_with_greeting():
    from app.services.filtering import filter_message

    result = filter_message(
        "Hello, I was charged twice for my subscription."
    )

    assert result.is_valid is True


def test_legitimate_feature_request_with_promotional_word():
    from app.services.filtering import filter_message

    result = filter_message(
        "I would like a discount option in my billing dashboard."
    )

    assert result.is_valid is True


def test_message_with_only_whitespace():
    from app.services.filtering import filter_message

    result = filter_message("   \n\t   ")

    assert result.is_valid is False


def test_legitimate_bug_report_containing_offer():
    from app.services.filtering import filter_message

    result = filter_message(
        "The checkout page crashes when I apply my discount offer."
    )

    assert result.is_valid is True


def test_assessment_pleasantry_is_rejected():
    result = filter_message("Hello, hope you are having a nice day!")
    assert result.is_valid is False


def test_greeting_plus_feature_request_is_accepted():
    result = filter_message("Hi team, please add dark mode to the mobile app.")
    assert result.is_valid is True
