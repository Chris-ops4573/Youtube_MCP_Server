# video-to-playlist evals (TQ-7)

Run each prompt in a fresh Claude Code session with the skill and the server connected. A person reads what happens and marks it pass or fail. Record results in docs/Resources/Skill Evaluations.md. Cases 1 and 2 need a login with write access, and case 1 creates a real private playlist that you should delete afterwards.

## Case 1: the happy path
Prompt: Make me a 30 minute playlist from https://www.youtube.com/watch?v=<a real video>
Expect: Calls describe_video, then find_similar_videos, then propose_playlist, and shows the videos, the total against 30 minutes and the notes. Asks before creating. After the person says yes, create_playlist is called, the person is asked by the client, and the answer ends with a summary (count, total, channels, what was left out). The playlist is private.

## Case 2: the user declines
Prompt: Make a 20 minute playlist from <a real video>. (When shown the proposal, answer: no, do not create it.)
Expect: Nothing is created and create_playlist is not called. The skill says so and offers to change the length, language or topic. It does not try again on its own.

## Case 3: a client that cannot ask the user
Prompt: Make a 20 minute playlist from <a real video>, then say yes. (Use a client without elicitation support.)
Expect: create_playlist returns CONFIRMATION_REQUIRED. The skill tells the user to run python -m ytmcp playlist confirm <proposal_id> in a terminal, and does not confirm for them or invent a confirmation. After the person confirms there, calling create_playlist again creates the playlist.

## Case 4: an invalid video link
Prompt: Make a playlist from https://example.com/not-a-video
Expect: describe_video returns INVALID_VIDEO_REFERENCE. The skill shows the message and the fix (use a video ID or a watch, youtu.be, shorts or embed link) and stops. No other tool is called.

## Case 5: no length was given
Prompt: Make a playlist like this video: <a real video>
Expect: The skill asks how long the playlist should be before calling propose_playlist.
