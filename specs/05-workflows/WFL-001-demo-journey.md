# WFL-001: End-to-end demo journey

Status: Accepted  
Owner: Team

## Requirements

### WFL-001 Load profile

The operator loads the canonical fictional demo profile and the interface shows
its three goal priorities.

### WFL-002 Discover candidates

Scout returns three candidates spanning the required demo categories, with
truthful live or fixture data modes and at least one real source in the final
demo. In connected mode, the Event Copilot coordinator creates a Band room,
adds Scout, Analyst, and Coach, and starts the run by mentioning Scout.

### WFL-003 Rank candidates

Analyst ranks the candidates and displays all three with scores, reasons,
citations, confidence, and scoring version. Scout hands the validated candidate
set to Analyst through a targeted Band message carrying the shared `run_id`.
The initial run may have no memory.

### WFL-004 Challenge and select

Coach states one risk or weakness in the top recommendation, after which the
user selects an event. Analyst hands the top recommendation to Coach through a
targeted Band message; Coach returns the validated result to the coordinator.
The connected UI shows the Band room and message provenance.

### WFL-005 Create and publish mission

The system creates a measurable Event Mission, previews its exact grounded
Markdown, and attempts cited.md publication. The final challenge-complete run
shows an inspectable remote result.

### WFL-006 Request playbook

The operator requests the detailed playbook through the x402 testnet boundary.
The UI shows the connected response or explicit demo mode without confusing
the two.

### WFL-007 Record outcome

The operator submits deliberate mixer feedback. The system validates it,
writes one EventEpisode, removes the attended mixer from consideration,
discovers a newly grounded live event, and ranks a fresh three-event slate with
the same scoring version. The new live event is shown as new, with its
memory-adjusted score and an evidence explanation instead of a fabricated
before rank. A connected run writes to Actian VectorAI DB and retrieves
same-user semantic matches with relevance provenance. An unavailable or
disabled Actian service writes to the labeled local JSON fallback and uses the
documented deterministic structured-event similarity rule.

## Critical success moment

```text
Initial ranking: mixer above workshop
→ deliberate mixer feedback
→ derived actual outcome
→ successful Actian or local-fallback episode write
→ attended mixer removed from future consideration
→ one newly grounded live event added
→ same profile + fresh three-event slate ranked
→ visible explanation names the prior mixer evidence on the new event
```

The after-state may be shown only after the episode write succeeds. If the
write fails, the product retains the initial ranking and reports that learning
did not occur. The final view must not present the attended event as a future
recommendation or assign a fictional before rank to the new live event.

## Demo controls

The recommended one-click controls are:

1. Load demo profile.
2. Run initial recommendation.
3. Generate Event Mission.
4. Request detailed playbook.
5. Simulate post-event feedback.
6. Rank the next live opportunity.

One page or one linear script is sufficient. Every external-action result must
show its actual mode. Ranking through reranking must also succeed locally when
Band or other external credentials are absent.
