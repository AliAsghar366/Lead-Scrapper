"""Compiled regex patterns for contact extraction."""
import re

EMAIL = re.compile(
    r"(?<![=\-\/\w])"                   # no char before
    r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"
    r"(?![^\s<>\"'])",
    re.IGNORECASE,
)

PHONE = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?){2,5}\d{3,6}"
)

SOCIAL = {
    "facebook": re.compile(
        r"https?://(?:www\.)?facebook\.com/(?!sharer|share|login|dialog)([^\s\"'<>/?#]+[^\s\"'<>/?#/])"
    ),
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/([^\s\"'<>/?#]+[^\s\"'<>/?#/])"
    ),
    "linkedin": re.compile(
        r"https?://(?:www\.)?linkedin\.com/(?:company|in|school)/([^\s\"'<>/?#]+[^\s\"'<>/?#/])"
    ),
    "twitter": re.compile(
        r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|home)([^\s\"'<>/?#]+[^\s\"'<>/?#/])"
    ),
    "youtube": re.compile(
        r"https?://(?:www\.)?youtube\.com/(?:channel|user|c|@)([^\s\"'<>/?#]+[^\s\"'<>/?#/])"
    ),
}

JUNK_EMAILS = frozenset({
    "example", "test", "noreply", "no-reply", "donotreply",
    "info@sentry", "user@example", "email@example",
    "privacy@", "legal@", "abuse@", "postmaster@",
})

JUNK_PHONES = frozenset({"1234567890", "0000000000", "9999999999"})
