import pytest

from wrapper.errors import (
    ArtifactError,
    CdlgExecutionError,
    ConfigurationError,
    PublicationError,
    ValidationError,
    exit_code_for,
)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConfigurationError("invalid YAML"), 2),
        (CdlgExecutionError("child failed"), 3),
        (ArtifactError("export failed"), 4),
        (ValidationError("invalid bundle"), 5),
        (PublicationError("cannot publish"), 6),
        (RuntimeError("unexpected"), 1),
    ],
)
def test_given_error_when_mapped_then_documented_exit_code_is_returned(error, expected):
    assert exit_code_for(error) == expected
