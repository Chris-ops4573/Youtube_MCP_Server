"""Errors with stable codes, so clients get clear messages (UI-3).

Each error has a `code` and a `remediation` that the tool layer returns
to the AI client. Messages must never include secrets such as the API key.
"""


class YtmcpError(Exception):
    code = "ERROR"
    remediation = "Try again. If it keeps failing, check the server logs."


class VideoNotFoundError(YtmcpError):
    """The video is private, deleted, or does not exist."""

    code = "VIDEO_NOT_FOUND"
    remediation = "Check that the video exists and is public, then try again."


class ApiKeyMissingError(YtmcpError):
    """No YouTube API key is configured."""

    code = "API_KEY_MISSING"
    remediation = "Set YOUTUBE_API_KEY in the .env file (see .env.example) and restart the server."


class QuotaExceededError(YtmcpError):
    """The request would go over the daily YouTube API quota (FR-7.1)."""

    code = "QUOTA_EXCEEDED"
    remediation = "The daily YouTube quota is used up. Try again after it resets at midnight Pacific time."


class YouTubeApiError(YtmcpError):
    """The YouTube API returned an error or could not be reached."""

    code = "YOUTUBE_API_ERROR"
    remediation = "Check your internet connection and API key, then try again."
