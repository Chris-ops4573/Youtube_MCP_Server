# Design Sequences

Design document 3 of 4 (SE-2). Who calls whom, in order.
Back to [[Design Components]]. Classes: [[Design Classes]].

## 1. Find similar videos (built, FR-1)
A cold request. With a warm cache the YouTube calls are skipped and it costs 0 units. `find_similar_channels` (FR-2) follows the same shape: see [[Channels]].

```mermaid
sequenceDiagram
  actor AI as AI client
  participant S as server.py
  participant T as tool
  participant V as service
  participant C as CachingProvider
  participant DB as SQLite database
  participant Y as YouTubeProvider
  participant G as YouTube API
  AI->>S: find_similar_videos(video, top_n)
  S->>T: similar_videos_tool
  T->>V: find_similar_videos
  V->>V: extract the 11 character ID
  V->>C: ensure_budget(102 units)
  C->>Y: ensure_budget(102 units)
  Note over Y: QuotaExceededError here means no API call is made
  V->>C: get_videos for the seed
  C->>DB: look up
  DB-->>C: miss
  C->>Y: get_videos
  Y->>G: videos.list (1 unit)
  G-->>Y: seed video
  C->>DB: save
  V->>C: search_videos(query)
  C->>DB: same search in the last hour?
  alt not cached
    C->>Y: search_videos
    Y->>G: search.list (100 units)
    Y->>G: videos.list (1 unit)
    C->>DB: save videos and search
  else cached
    DB-->>C: video IDs (0 units)
  end
  V->>V: rank by TF-IDF and weights
  V-->>T: scored videos
  T-->>S: results or error dict
  S-->>AI: JSON
```

## 2. Sign in (built, FR-6.1)
```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli.py
  participant A as AuthService
  participant L as LoopbackReceiver
  participant B as Browser
  participant G as Google
  participant K as OS keyring
  U->>CLI: python -m ytmcp auth login
  CLI->>A: login()
  A->>A: make PKCE verifier, challenge and state
  A->>L: listen on 127.0.0.1, any free port
  A->>B: open the Google sign-in link
  B->>G: user signs in and approves read-only access
  G-->>B: redirect to 127.0.0.1 /callback with code and state
  B->>L: GET /callback
  L-->>A: code and state
  A->>A: reject unless state matches
  A->>G: swap code and verifier for tokens
  G-->>A: access token and refresh token
  A->>K: save token
  A-->>CLI: signed in
  CLI-->>U: Signed in, read-only
```

## 3. Stay signed in (built, FR-6.2)
Later features call `get_access_token()`. The user is only asked to sign in again if Google refuses to renew (for example the 7 day Testing-mode limit).

```mermaid
sequenceDiagram
  participant F as a feature
  participant A as AuthService
  participant K as OS keyring
  participant G as Google
  F->>A: get_access_token()
  A->>K: load token
  alt no token
    A-->>F: AUTH_REQUIRED, sign in
  else token still valid
    A-->>F: access token
  else token expired
    A->>G: refresh with the refresh token
    alt Google renews it
      G-->>A: new access token
      A->>K: save
      A-->>F: access token
    else invalid_grant
      A->>K: delete the saved login
      A-->>F: AUTH_REQUIRED, sign in again
    end
  end
```

## 4. Create a playlist (built, FR-5)
A person must approve, and the AI has no way to approve (FR-5.5). There are two ways a person confirms: the client asks the user, or the user confirms in a terminal. See [[ADR-013 Playlist creation needs a person's confirmation]] and [[Playlist]].

```mermaid
sequenceDiagram
  actor U as User
  participant AI as AI client
  participant S as MCP server
  participant DB as SQLite proposals
  participant T as Terminal
  participant G as YouTube API
  U->>AI: Make me a 1 hour Rust playlist
  AI->>S: propose_playlist(topic, total_minutes, ...)
  S->>S: validate the settings, no API call yet
  S->>G: search.list and videos.list (101 units)
  S->>S: pick videos within 10 percent of the target
  S->>DB: save the proposal (id, hash, 15 minute expiry)
  S-->>AI: the proposal, nothing created yet
  AI-->>U: show the videos and totals and ask
  AI->>S: create_playlist(proposal_id, content_hash)
  S->>DB: load it, check expiry, hash and not used
  alt the client supports elicitation
    S->>U: Create the PRIVATE playlist? (asked through the client)
    U-->>S: yes or no
  else the client cannot ask
    S-->>AI: CONFIRMATION_REQUIRED with the terminal command
    U->>T: python -m ytmcp playlist confirm id
    T->>DB: mark confirmed (needs a real terminal)
    AI->>S: create_playlist again
  end
  S->>S: check quota (50 plus 50 per video) and write permission
  S->>DB: claim the proposal, only one caller can
  S->>G: playlists.insert (private)
  S->>G: playlistItems.insert for each video, no retries
  S->>DB: save the result
  S-->>AI: the playlist URL, or a report of partial failures
```

### Proposal states
No write to YouTube happens before `Creating`. A proposal can be used once.

```mermaid
stateDiagram-v2
  [*] --> Proposed: propose_playlist
  Proposed --> Expired: 15 minutes pass
  Proposed --> Declined: user says no
  Proposed --> Confirmed: person confirms in the terminal
  Proposed --> Creating: user says yes to the client question
  Confirmed --> Expired: 15 minutes pass
  Confirmed --> Declined: user says no
  Confirmed --> Creating: create_playlist
  Creating --> Created: all videos added
  Creating --> PartiallyCreated: some videos not added
  Creating --> Failed: playlist not created
  Expired --> [*]
  Declined --> [*]
  Created --> [*]
  PartiallyCreated --> [*]
  Failed --> [*]
```

## 5. Recommend videos (built, FR-3)
Reads the user's own account with the read-only login, builds a taste profile, searches once. See [[Recommendations]].

```mermaid
sequenceDiagram
  actor AI as AI client
  participant T as tool
  participant S as service
  participant P as VideoProvider
  participant A as AccountProvider
  participant G as YouTube API
  AI->>T: recommend_videos(top_n)
  T->>S: recommend_videos
  S->>P: ensure_budget(127 units)
  Note over S,P: QuotaExceededError here means no call is made
  S->>A: liked_videos(250)
  A->>G: channels.list and playlistItems.list (read-only login)
  S->>A: subscriptions(200)
  A->>G: subscriptions.list
  alt no likes and no subscriptions
    S-->>T: NOT_ENOUGH_HISTORY
  else
    S->>A: playlist_video_ids(10)
    A->>G: playlists.list and playlistItems.list
    S->>P: get_videos(liked IDs)
    P->>G: videos.list (cached)
    S->>S: build the taste profile (top words, categories, channels)
    S->>P: search_videos(top words, 50)
    P->>G: search.list (100 units) and videos.list
    S->>S: drop liked and saved videos, score, add a reason to each
    S-->>T: results and counts
  end
  T-->>AI: JSON with counts only about the user's data
```

## 6. Analyse engagement (built, FR-4)
Reads only the sources the user chose, then works out statistics. See [[Engagement]].

```mermaid
sequenceDiagram
  actor AI as AI client
  participant T as tool
  participant S as service
  participant P as VideoProvider
  participant A as AccountProvider
  participant G as YouTube API
  AI->>T: analyze_engagement(sources, period_months, compare)
  T->>T: check the arguments, no API call yet
  T->>S: analyze_engagement
  S->>P: ensure_budget(up to 47 units)
  Note over S,P: QuotaExceededError here means no call is made
  S->>A: liked_videos(500), subscriptions(200), playlist_video_ids(10)
  A->>G: read-only login: likes, subscriptions, playlists
  S->>P: get_videos(liked and saved IDs)
  P->>G: videos.list (cached)
  S->>P: category_names()
  P->>G: videoCategories.list (1 unit)
  S->>S: top lists, monthly trend, duration split, optional comparison
  S-->>T: statistics, caveats and the watch history note
  T-->>AI: JSON with statistics only
```
