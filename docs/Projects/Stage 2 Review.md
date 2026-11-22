# Stage 2 Review

Stage 2 = Design. Deliverables from the SRS (section 6): design docs, `brain-refine`, `brain-query`, `local-check`.

## Deliverables
- [x] Design docs with UML and ER: [[Design Components]], [[Design Classes]], [[Design Sequences]], [[Design Data]]
- [x] `local-check` skill (SK-2): see [[Testing]]
- [ ] `brain-refine` skill (SK-3)
- [ ] `brain-query` skill (SK-3)
- [x] ADRs cite brain notes (SE-3): every ADR in the [[Index]] has a `Cites:` line
- [x] Development plan (SE-4): [[Development Plan]]

## TBDs due by Stage 2
| TBD | Question | Result |
|---|---|---|
| TBD-1 | Language and libraries | Python 3.11+: [[ADR-008 Python 3.11 and libraries]] |
| TBD-3 | Are like dates available? | Yes, from the likes playlist: [[ADR-010 Like dates from the likes playlist]] |
| TBD-4 | stdio or HTTP? | stdio only: [[ADR-009 Stdio transport only]] |
| TBD-9 | Transcripts? | No, metadata only: [[ADR-011 Metadata only, no transcripts]] |
| TBD-8 | Re-check API unit costs | **Open.** Needs a person to confirm in Google's Quota Calculator, see [[Quota]] |

## Done early (Stage 3 and later work)
FR-1, FR-2, FR-7 and the FR-6 sign-in core are built and tested. See [[Traceability]].

## Not part of this review
- TBD-2, TBD-5, TBD-6 (Stage 3) and TBD-7 (cover page names) are still open: see [[Requirements]].
- The CI check for notes and skills (SRS section 6) is planned, not built: see [[Development Plan]].
