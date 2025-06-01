class SuggestionException(Exception):
    """Base exception class"""


class MessageTooLong(SuggestionException):
    """The content provided was too long."""

    def __init__(self, text: str):
        self.message_text = text


class MissingTranslation(SuggestionException):
    """The en_GB translation file is missing a translation."""


class InvalidFileType(SuggestionException):
    """The attempted image upload was invalid."""


class MissingQueueChannel(SuggestionException):
    """Tried to send a queued suggestion to a non-existent channel."""
