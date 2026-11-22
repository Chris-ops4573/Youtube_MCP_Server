# ADR-001 Provider interface

Status: Accepted

## Context
The SRS requires all YouTube access to go through one interface (SE-6, SI-1),
and CI tests must not call the live API (TQ-5).

## Decision
Define an abstract `VideoProvider` with `get_videos`, `search_videos` and
`get_channels`. Services only talk to this interface. A `FixtureProvider`
reads JSON fixtures for tests.

## Consequences
- Tests run offline, free of quota.
- A live provider can be added later without changing services.
- Every new kind of YouTube data needs a new method on the interface.

Cites: [[Providers]], [[Architecture]]
