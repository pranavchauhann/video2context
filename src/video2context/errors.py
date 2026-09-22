class Video2ContextError(Exception):
    """An actionable, safe-to-display failure."""


class ConfigurationError(Video2ContextError):
    pass


class MediaError(Video2ContextError):
    pass


class ProviderError(Video2ContextError):
    pass


class OutputError(Video2ContextError):
    pass
