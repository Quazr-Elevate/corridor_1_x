import re

PINCODE_REGEX = re.compile(r"^[1-9][0-9]{5}$")
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Person name: starts with a letter, then letters / spaces / apostrophes /
# hyphens / periods. Blocks digits and other special characters. Allows
# "O'Brien", "Smith-Jones", "J. Sharma".
PERSON_NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z\s.'-]{1,99}$")


def is_valid_pincode(v: str) -> bool:
    return bool(PINCODE_REGEX.match(v.strip()))


def is_valid_email(v: str) -> bool:
    return bool(EMAIL_REGEX.match(v.strip()))


def is_valid_person_name(v: str) -> bool:
    return bool(PERSON_NAME_REGEX.match(v.strip()))
