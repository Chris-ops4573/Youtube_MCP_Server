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


class ChannelNotFoundError(YtmcpError):
    """The channel does not exist or has no public page."""

    code = "CHANNEL_NOT_FOUND"
    remediation = "Check the channel ID, @handle or URL, then try again."


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

    def __init__(self, message: str, reason: str | None = None):
        super().__init__(message)
        self.reason = reason  # YouTube's error reason, e.g. "playlistNotFound"


class OAuthConfigError(YtmcpError):
    """The Google OAuth client ID is not configured."""

    code = "OAUTH_NOT_CONFIGURED"
    remediation = (
        "Set YTMCP_OAUTH_CLIENT_ID and YTMCP_OAUTH_CLIENT_SECRET in the .env file "
        "(see .env.example) and try again."
    )


class AuthRequiredError(YtmcpError):
    """The user is not signed in, or their Google login has expired (FR-6.2)."""

    code = "AUTH_REQUIRED"
    remediation = "Run `python -m ytmcp auth login` to sign in with Google, then try again."


class AuthFailedError(YtmcpError):
    """Signing in failed (denied, timed out, bad response or no keyring)."""

    code = "AUTH_FAILED"
    remediation = (
        "Run `python -m ytmcp auth login` again. If it keeps failing, check your "
        "OAuth client settings in .env."
    )


class InvalidConstraintsError(YtmcpError):
    """Playlist constraints failed validation (FR-5.1). `fields` maps each bad field to why."""

    code = "INVALID_CONSTRAINTS"
    remediation = "Fix the fields listed under `fields` and try again."

    def __init__(self, message: str, fields: dict[str, str]):
        super().__init__(message)
        self.fields = fields


class NoVideosFoundError(YtmcpError):
    """No video matched the topic and constraints."""

    code = "NO_VIDEOS_FOUND"
    remediation = "Try a broader topic, a longer maximum video length, or no language filter."


class ProposalNotFoundError(YtmcpError):
    code = "PROPOSAL_NOT_FOUND"
    remediation = "Create a new proposal with propose_playlist."


class ProposalExpiredError(YtmcpError):
    code = "PROPOSAL_EXPIRED"
    remediation = "Proposals last 15 minutes. Create a new one with propose_playlist."


class ProposalMismatchError(YtmcpError):
    """The content hash does not match the saved proposal (FR-5.5)."""

    code = "PROPOSAL_MISMATCH"
    remediation = "Use the proposal_id and content_hash exactly as returned by propose_playlist."


class ProposalUsedError(YtmcpError):
    """The proposal was already created, is being created, failed or was declined."""

    code = "PROPOSAL_ALREADY_USED"
    remediation = "Create a new proposal with propose_playlist if you want another playlist."


class ConfirmationRequiredError(YtmcpError):
    """A person has not confirmed this proposal (FR-5.5)."""

    code = "CONFIRMATION_REQUIRED"

    def __init__(self, proposal_id: str):
        super().__init__("A person has to confirm this playlist before it can be created.")
        self.remediation = (
            "This client cannot ask the user directly. Ask the user to run "
            f"`python -m ytmcp playlist confirm {proposal_id}` in a terminal, then call "
            "create_playlist again with the same proposal_id and content_hash."
        )


class WriteAccessRequiredError(YtmcpError):
    """Creating playlists needs a Google login with write permission (FR-6.1)."""

    code = "WRITE_ACCESS_REQUIRED"
    remediation = (
        "Run `python -m ytmcp auth login --write` to allow creating playlists, then call "
        "create_playlist again. The proposal stays valid for its 15 minutes."
    )


class YouTubeChannelRequiredError(YtmcpError):
    """The Google account has no YouTube channel, so it cannot own playlists (FR-5.6)."""

    code = "YOUTUBE_CHANNEL_REQUIRED"
    remediation = "Create a YouTube channel for this Google account at youtube.com, then try again."


class PlaylistWritesDisabledError(YtmcpError):
    """Playlist creation is switched off (fixture mode)."""

    code = "PLAYLIST_WRITES_DISABLED"
    remediation = "Set YTMCP_PROVIDER=youtube in .env and restart the server to create real playlists."


class AccountUnavailableError(YtmcpError):
    """This feature needs the user's Google account, but the server is in fixture mode."""

    code = "ACCOUNT_NOT_AVAILABLE"
    remediation = (
        "This uses your own YouTube data. Set YTMCP_PROVIDER=youtube in .env (not fixture mode), "
        "sign in with `python -m ytmcp auth login`, and restart the server."
    )


class NotEnoughHistoryError(YtmcpError):
    """The user has no likes or subscriptions to build a taste profile from (FR-3)."""

    code = "NOT_ENOUGH_HISTORY"
    remediation = "Like some videos or subscribe to some channels on YouTube first, then try again."
