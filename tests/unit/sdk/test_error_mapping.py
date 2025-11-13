from domain.errors import DomainError, ValidationError
from py_accountant.sdk.errors import (
    DomainViolation,
    UnexpectedError,
    UserInputError,
    map_exception,
)


def test_map_validation_error_to_user_input():
    e = map_exception(ValidationError("bad"))
    assert isinstance(e, UserInputError)
    assert str(e) == "bad"


def test_map_domain_error_to_domain_violation():
    e = map_exception(DomainError("rule"))
    assert isinstance(e, DomainViolation)


def test_map_value_error_to_user_input():
    e = map_exception(ValueError("oops"))
    assert isinstance(e, UserInputError)


def test_map_other_to_unexpected():
    e = map_exception(RuntimeError("boom"))
    assert isinstance(e, UnexpectedError)

