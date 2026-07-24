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
demo.

### WFL-003 Rank candidates

Analyst ranks the candidates and displays all three with scores, reasons,
citations, confidence, and scoring version. The initial run may have no memory.

### WFL-004 Challenge and select

Coach states one risk or weakness in the top recommendation, after which the
user selects an event.

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
writes one local EventEpisode, reruns the same candidate set with the same
scoring version, and shows the workshop overtake the mixer with score/rank
deltas and an evidence explanation.

## Critical success moment

```text
Initial ranking: mixer above workshop
→ deliberate mixer feedback
→ derived actual outcome
→ successful local episode write
→ same profile + candidates reranked
→ workshop above mixer
→ visible explanation names the feedback evidence
```

The after-state may be shown only after the episode write succeeds. If the
write fails, the product retains the initial ranking and reports that learning
did not occur.

## Demo controls

The recommended one-click controls are:

1. Load demo profile.
2. Run initial recommendation.
3. Generate Event Mission.
4. Request detailed playbook.
5. Simulate post-event feedback.
6. Show improved recommendations.

One page or one linear script is sufficient. Every external-action result must
show its actual mode. Ranking through reranking must also succeed locally when
external credentials are absent.
