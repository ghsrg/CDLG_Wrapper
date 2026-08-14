class WrapperError(Exception):
    """Base class for expected wrapper failures."""


class ConfigurationError(WrapperError):
    pass


class CdlgExecutionError(WrapperError):
    pass


class ArtifactError(WrapperError):
    pass


class ValidationError(WrapperError):
    pass


class PublicationError(WrapperError):
    pass


def exit_code_for(error: BaseException) -> int:
    if isinstance(error, ConfigurationError):
        return 2
    if isinstance(error, CdlgExecutionError):
        return 3
    if isinstance(error, ArtifactError):
        return 4
    if isinstance(error, ValidationError):
        return 5
    if isinstance(error, PublicationError):
        return 6
    return 1
