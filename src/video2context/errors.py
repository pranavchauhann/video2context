class Video2ContextError(Exception):
    """An actionable, safe-to-display failure."""


class ConfigurationError(Video2ContextError):
    pass


class MediaError(Video2ContextError):
    pass


class ProviderError(Video2ContextError):
    pass


class ProviderAuthError(ProviderError):
    """Credentials were rejected; retrying other requests would only repeat the failure."""


class OutputError(Video2ContextError):
    pass
