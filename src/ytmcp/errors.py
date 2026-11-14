"""Errors with stable codes, so clients get clear messages (UI-3)."""


class YtmcpError(Exception):
    code = "ERROR"


class VideoNotFoundError(YtmcpError):
    """The video is private, deleted, or does not exist."""

    code = "VIDEO_NOT_FOUND"