class ClipForgeError(Exception):
    """An error with a message that is safe and useful to show to the user."""


class MediaError(ClipForgeError):
    pass


class ModelError(ClipForgeError):
    pass


class ImportError_(ClipForgeError):
    pass


class CancelledError(Exception):
    pass
