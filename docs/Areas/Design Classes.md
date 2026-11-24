# Design Classes

Design document 2 of 4 (SE-2). Class diagrams of what exists in the code today.
Back to [[Design Components]].

## Providers, cache and data
`CachingProvider` wraps another provider and has the same interface, so services cannot tell them apart ([[ADR-005 SQLite cache]]).

```mermaid
classDiagram
  class VideoProvider {
    <<abstract>>
    +get_videos(video_ids) list~Video~
    +search_videos(query, max_results) list~Video~
    +get_channels(channel_ids) list~Channel~
    +get_channel_by_handle(handle) Channel
    +search_channels(query, max_results) list~Channel~
    +get_recent_uploads(channel_id, max_results) list~str~
    +ensure_budget(units)
  }
  class FixtureProvider
  class YouTubeProvider
  class CachingProvider
  class Cache
  class QuotaTracker
  class Video {
    +str id
    +str title
    +str description
    +str channel_id
    +str channel_title
    +list tags
    +str category_id
    +str language
    +int duration_seconds
    +bool is_live
  }
  class Channel {
    +str id
    +str title
    +str description
    +list keywords
    +int subscriber_count
    +str handle
    +list topics
  }
  VideoProvider <|-- FixtureProvider
  VideoProvider <|-- YouTubeProvider
  VideoProvider <|-- CachingProvider
  CachingProvider o-- VideoProvider : wraps
  CachingProvider --> Cache : reads and writes
  YouTubeProvider --> QuotaTracker : counts every call
  QuotaTracker --> Cache : saves daily count
  VideoProvider ..> Video
  VideoProvider ..> Channel
```

## Sign-in (FR-6)
`AuthService` is the only thing later features call: `get_access_token()` returns a valid token or raises `AUTH_REQUIRED`.

```mermaid
classDiagram
  class AuthService {
    +login(scopes, timeout) Token
    +get_access_token(scope) str
    +status() dict
    +logout() dict
  }
  class OAuthClient {
    +build_auth_url(redirect_uri, scopes, state, challenge) str
    +exchange_code(code, verifier, redirect_uri) Token
    +refresh(token) Token
    +revoke(token) bool
  }
  class OAuthConfig {
    +str client_id
    +str client_secret
  }
  class TokenStore {
    +load() Token
    +save(token)
    +delete() bool
  }
  class Token {
    +str access_token
    +str refresh_token
    +float expires_at
    +tuple scopes
    +expired(now) bool
  }
  class LoopbackReceiver {
    +redirect_uri str
    +wait(timeout) dict
  }
  AuthService --> OAuthClient
  AuthService --> TokenStore
  AuthService --> LoopbackReceiver : one per login
  OAuthClient --> OAuthConfig
  TokenStore --> Token : keeps in OS keyring
```

## Playlists (FR-5)
The writer is separate from `VideoProvider`. It can only create ([[Playlist]]).

```mermaid
classDiagram
  class PlaylistWriter {
    <<abstract>>
    +ensure_write_access()
    +ensure_budget(units)
    +create_playlist(title, description) str
    +add_video(playlist_id, video_id)
  }
  class YouTubePlaylistWriter
  class ProposalStore {
    +save(proposal)
    +get(proposal_id) Proposal
    +confirm(proposal_id, now) bool
    +claim(proposal_id, now, from_status) bool
    +finish(proposal_id, status, playlist_id)
    +decline(proposal_id) bool
  }
  class Proposal {
    +str id
    +str content_hash
    +str title
    +str description
    +tuple videos
    +dict constraints
    +float expires_at
    +str status
  }
  class Constraints {
    +str topic
    +int total_minutes
    +int max_video_minutes
    +str language
    +str title
  }
  class Selection {
    +list videos
    +int total_seconds
    +bool meets_target
    +list notes
  }
  PlaylistWriter <|-- YouTubePlaylistWriter
  YouTubePlaylistWriter --> QuotaTracker : counts every call
  YouTubePlaylistWriter --> AuthService : gets a write token
  ProposalStore --> Cache : proposals table
  ProposalStore --> Proposal
  Constraints ..> Selection : select_videos
```

## Errors
Every error has a stable `code` and a `remediation` the tool returns to the AI client (UI-3). See [[Errors]].

```mermaid
classDiagram
  class YtmcpError {
    +code
    +remediation
  }
  YtmcpError <|-- VideoNotFoundError
  YtmcpError <|-- ChannelNotFoundError
  YtmcpError <|-- ApiKeyMissingError
  YtmcpError <|-- QuotaExceededError
  YtmcpError <|-- YouTubeApiError
  YtmcpError <|-- OAuthConfigError
  YtmcpError <|-- AuthRequiredError
  YtmcpError <|-- AuthFailedError
  YtmcpError <|-- InvalidConstraintsError
  YtmcpError <|-- NoVideosFoundError
  YtmcpError <|-- ProposalNotFoundError
  YtmcpError <|-- ProposalExpiredError
  YtmcpError <|-- ProposalMismatchError
  YtmcpError <|-- ProposalUsedError
  YtmcpError <|-- ConfirmationRequiredError
  YtmcpError <|-- WriteAccessRequiredError
  YtmcpError <|-- YouTubeChannelRequiredError
  YtmcpError <|-- PlaylistWritesDisabledError
```

The services and tools are plain functions, not classes (`find_similar_videos`, `find_similar_channels`, `similar_videos_tool`, `similar_channels_tool`), so they are not drawn here. Their flow is in [[Design Sequences]].
