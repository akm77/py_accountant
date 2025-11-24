import pytest

from py_accountant.domain.errors import DomainError, ValidationError


def test_errors_raise_and_inherit():
    # DomainError behaves like base Exception
    with pytest.raises(DomainError) as de:
        raise DomainError("domain failure")
    assert isinstance(de.value, Exception)
    assert isinstance(de.value, DomainError)
    assert "domain failure" in str(de.value)

    # ValidationError inherits from DomainError
    with pytest.raises(ValidationError) as ve:
        raise ValidationError("validation failed")
    assert isinstance(ve.value, ValidationError)
    assert isinstance(ve.value, DomainError)
    assert "validation failed" in str(ve.value)

