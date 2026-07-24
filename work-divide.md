## Two-person build plan: **Conference Connector / EventROI**

The safest split is by **stable modules**, not by random tasks. One person owns the **intelligence and learning loop**; the other owns the **agent orchestration, user flow, and real-world actions**.

Both work against a shared JSON contract agreed in the first 15 minutes. That prevents the classic hackathon experience of merging two individually functional systems into one collectively non-functional system.

---

# Team roles

## Person 1 — Intelligence & Learning Lead

Owns:

* Event ingestion and normalization
* Pioneer extraction and scoring
* Actian agent memory
* Feedback-to-learning logic
* Event ranking
* Seeded historical outcomes
* Before-versus-after improvement demonstration

Primary output:

```text
Raw event page
→ structured event
→ predicted outcomes
→ personalized ranking
→ memory-informed reranking
```

## Person 2 — Product, Agents & Actions Lead

Owns:

* Band agent-to-agent communication
* User profile and goal input
* Recommendation UI or API
* Event Mission generation
* Feedback form
* Publishing output to cited.md
* x402-paid endpoint
* Demo flow and presentation

Primary output:

```text
User goals
→ agents coordinate
→ recommendation displayed
→ event mission published
→ feedback collected
→ paid detailed report exposed
```

---

# Rule zero: agree on the contract first

Before either person starts coding, create one shared file:

```text
shared/contracts.py
```

Or, for TypeScript:

```text
shared/types.ts
```

Neither person changes this file without telling the other.

## Shared event schema

```json
{
  "event_id": "evt_001",
  "title": "Self-Improving AI Agents Hackathon",
  "description": "Build autonomous agents that evolve...",
  "source_url": "https://example.com/event",
  "source_name": "Luma",
  "start_time": "2026-07-24T11:00:00-07:00",
  "location": "San Francisco",
  "themes": ["AI agents", "hackathon"],
  "format": "hackathon",
  "interaction_level": 0.9,
  "knowledge_depth": 0.8,
  "estimated_crowd_size": 100,
  "cost_usd": 0
}
```

## Shared recommendation schema

```json
{
  "event_id": "evt_001",
  "scores": {
    "networking": 82,
    "knowledge": 91,
    "opportunity": 76,
    "personal_fit": 85,
    "friction": 32,
    "overall": 84
  },
  "reasons": [
    "Hands-on format creates repeated interaction.",
    "Topic closely matches the user's AI-agent learning goal."
  ],
  "similar_past_events": ["episode_003", "episode_007"],
  "confidence": 0.83,
  "citations": [
    {
      "claim": "The event is a hands-on agent hackathon.",
      "url": "https://example.com/event"
    }
  ]
}
```

## Shared feedback schema

```json
{
  "event_id": "evt_001",
  "meaningful_conversations": 5,
  "contacts_exchanged": 3,
  "followups_sent": 2,
  "meetings_booked": 1,
  "questions_answered": 3,
  "actionable_insights": 2,
  "opportunities_created": 1,
  "energy_after": 7,
  "overall_value": 9,
  "free_text_feedback": "Hands-on events work better than mixers."
}
```

These three objects are the border between both people’s work.

---

# Repository structure

```text
conference-connector/
│
├── shared/
│   ├── contracts.py
│   ├── sample_events.json
│   ├── sample_profile.json
│   └── sample_feedback.json
│
├── intelligence/                 # Person 1 owns
│   ├── event_extractor.py
│   ├── pioneer_client.py
│   ├── actian_memory.py
│   ├── scorer.py
│   ├── learning_loop.py
│   └── seed_episodes.py
│
├── product/                      # Person 2 owns
│   ├── band_agents.py
│   ├── event_mission.py
│   ├── cited_publisher.py
│   ├── payment_endpoint.py
│   └── ui.py
│
├── integration/
│   ├── pipeline.py
│   └── demo_scenario.py
│
├── tests/
│   ├── test_contracts.py
│   └── test_demo_flow.py
│
├── .env.example
├── requirements.txt
└── README.md
```

### Ownership rule

* Person 1 edits `intelligence/`.
* Person 2 edits `product/`.
* Either may edit `integration/`, but only while pairing or after announcing it.
* Changes to `shared/` require agreement.
* Never both edit the same file at the same time.

---

# 12:30 p.m.–4:00 p.m. schedule

This is a compressed build window. Protect the one feature that proves the challenge statement: **real feedback changes the agent's next recommendation**. Everything else supports that moment.

## 12:30–12:45 — Pair together and lock the contract

Work on one laptop or screen-share.

Agree on:

* Product name and one demo user profile
* Three sample event categories
* The event, recommendation and feedback schemas above
* Which API keys currently work
* The exact final demo sequence
* Which person owns each integration file

Use one simple success score:

```text
Actual event success =
30% networking
+ 30% knowledge
+ 30% opportunities
+ 10% personal fit
```

For the demo, networking can use:

```text
Meaningful conversations
+ contacts exchanged
+ 2 × meetings booked
```

Create the shared contracts and mock files immediately:

```text
shared/contracts.py
shared/sample_events.json
shared/sample_profile.json
shared/mock_recommendations.json
shared/sample_feedback.json
```

Do not spend time perfecting the scoring mathematics. The goal is to make measured outcomes visibly change future rankings.

---

## 12:45–1:25 — Parallel build phase 1: working vertical slice

### Person 1: local intelligence pipeline

Tasks:

1. Create 8–10 sample events.
2. Normalize them into the shared schema.
3. Implement the first scoring function.
4. Connect Pioneer for structured extraction if credentials work.
5. Add a cached extraction fallback.
6. Return three ranked recommendations matching the shared contract.

Minimum success:

```python
recommendations = rank_events(
    events=sample_events,
    profile=sample_profile
)
```

The function must work without Pioneer by using cached sample outputs.

### Person 2: product shell

Tasks:

1. Build a basic Streamlit or lightweight web interface.
2. Add networking, knowledge and opportunity goal inputs.
3. Render three events from `shared/mock_recommendations.json`.
4. Let the user select an event.
5. Display a basic Event Mission.
6. Add a minimal post-event feedback form.

Minimum success:

```text
Load demo profile
→ show three ranked events
→ select an event
→ show Event Mission
→ submit feedback
```

Person 2 does **not** wait for Person 1's scoring code. Both implementations target the agreed JSON contract.

---

## 1:25–1:40 — Integration checkpoint 1

Pair together and connect:

```text
Person 1 rank_events()
→ Person 2 recommendation UI
```

Test one event first, then all three.

Check:

* Field names match.
* Scores and explanations render.
* Missing optional data does not crash the UI.
* Citations remain attached.
* The mock-data fallback still works.

Commit and tag the working vertical slice:

```bash
git tag vertical-slice-1
```

This is the fallback demo if later integrations fail.

---

## 1:40–2:20 — Parallel build phase 2: self-improvement and agents

### Person 1: Actian memory and evolution

Tasks:

1. Store or simulate eight seeded event episodes.
2. Retrieve similar past events before scoring.
3. Adjust scores using observed outcomes.
4. Implement feedback ingestion.
5. Produce before-and-after recommendation fixtures.

Core functions:

```python
def retrieve_similar_experiences(
    user_id: str,
    event: Event
) -> list[EventEpisode]:
    ...
```

```python
def record_event_outcome(
    user_id: str,
    event: Event,
    feedback: EventFeedback
) -> None:
    ...
```

```python
def rank_events_with_memory(
    user_profile: UserProfile,
    events: list[Event]
) -> list[Recommendation]:
    ...
```

Prepare one deliberate learning example:

* A large mixer initially scores 88.
* Historical memories show many conversations but no follow-ups.
* The mixer falls to 65.
* A small workshop rises from 76 to 91.

That visible ranking change is the heart of the pitch. If Actian is unavailable, use seeded local memories and label the status as `demo fallback`.

### Person 2: Band coordination and measurable mission

Create three agents:

#### Scout

```text
Find and normalize candidate events relevant to the user's goals.
```

#### Analyst

```text
Evaluate candidate events using the user's goals and previous outcomes.
```

#### Coach

```text
Challenge the recommendation and create a measurable event mission.
```

Show a short, visible handoff:

```text
Scout → Analyst:
I found candidate events. Evaluate them for networking,
learning and opportunity outcomes.

Analyst → Coach:
The workshop ranks first based on prior outcomes.
Challenge the choice and identify weaknesses.

Coach → User:
Attend with three measurable objectives.
```

Keep the underlying intelligence directly callable so a Band failure does not break the product.

---

## 2:20–2:35 — Integration checkpoint 2: prove the learning loop

Pair together and connect:

```text
Feedback form
→ record_event_outcome()
→ Actian or seeded fallback
→ rerun ranking
→ updated result in UI
```

The UI must visibly show:

```text
Before feedback: Mixer ranked #1
After learning: Workshop ranked #1
```

Add a short explanation panel:

```text
Why the recommendation changed

Past large mixers produced conversations but no follow-up
meetings. Participatory workshops produced fewer contacts but
more continuing relationships.
```

Commit and tag:

```bash
git tag learning-loop-working
```

Do not continue until this path works locally.

---

## 2:35–3:05 — Parallel build phase 3: publish, transact and slow loop

### Person 1: Pioneer slow loop and evaluation

Build only the credible minimum:

1. Create a small labeled Pioneer dataset.
2. Label events for networking, learning, opportunity and personal fit.
3. Launch an evaluation or training job if the service is available.
4. Save the job status and evaluation output.
5. Keep the application running on base inference or cached extraction.

The demo explanation is:

> “The fast loop changes recommendations immediately using Actian memory. The slow loop adds verified outcomes to Pioneer and periodically evaluates a specialized scoring model.”

A running Pioneer job is enough when the real-time memory loop already works.

### Person 2: cited.md and payment action

Tasks:

1. Generate a sourced markdown Event Mission.
2. Publish or prepare it through the cited.md workflow.
3. Expose a free recommendations endpoint.
4. Expose a detailed success-playbook endpoint.
5. Put the detailed playbook behind x402 testnet payment if time permits.

Suggested endpoints:

```http
GET /api/recommendations
GET /api/events/{event_id}/playbook
```

The free response includes:

* Event title
* Scores
* Short explanation
* Source

The detailed playbook includes:

* People to target
* Questions to ask
* Networking and learning objectives
* Follow-up strategy

Payments must not block the demo:

```env
PAYMENTS_ENABLED=false
```

When disabled, return:

```json
{
  "payment_mode": "demo"
}
```

---

## 3:05–3:20 — Integration checkpoint 3: full demo flow

Pair together and run:

1. Load the demo user profile.
2. Scout returns candidate events.
3. Analyst ranks them using prior outcomes.
4. Coach challenges the top result.
5. The user selects an event.
6. The app generates an Event Mission.
7. The mission is published or shown as cited.md output.
8. The detailed playbook endpoint is requested.
9. Post-event feedback is entered.
10. The outcome is stored.
11. The ranking changes for an evidence-based reason.

Anything that does not serve this sequence is cut.

---

## 3:20–3:35 — Reliability and fallback work

### Person 1

Prepare:

```text
sample_events.json
pioneer_extractions.json
actian_memories.json
recommendations_before.json
recommendations_after.json
```

Add short timeouts and fallbacks:

```python
try:
    return call_pioneer(event)
except Exception:
    return cached_extraction(event.event_id)
```

```python
try:
    memories = query_actian(event)
except Exception:
    memories = load_seeded_memories()
```

### Person 2

Add one-click demo controls:

* `Load demo profile`
* `Run initial recommendation`
* `Simulate post-event feedback`
* `Show improved recommendations`
* `Generate Event Mission`

Add a visible status panel:

```text
Pioneer: connected | demo fallback
Actian memory: 8 experiences | demo fallback
Band agents: 3 active | direct-call fallback
cited.md: published | local preview
x402: testnet enabled | demo mode
```

Only display statuses that reflect reality.

---

## 3:35–3:50 — Presentation rehearsal

Run the demo twice without editing code.

### Person 2 opens and demonstrates the product

> “Event platforms optimize for clicks and registrations. We optimize for whether attending the event actually produced knowledge, relationships and opportunities.”

Cover:

* The user's goal
* Band agent coordination
* Event Mission
* cited.md publication
* x402 monetization

### Person 1 demonstrates and explains learning

> “The agent initially recommends this large mixer. Actian then retrieves previous experiences showing high conversation counts and zero follow-up meetings, so the agent promotes this smaller workshop.”

Cover:

* Structured event data
* Memory retrieval
* Before-and-after ranking
* Immediate feedback loop
* Pioneer slow improvement loop

### Person 2 closes with the real-world action

> “The system creates a measurable attendance mission, publishes a grounded report and offers a detailed success playbook through an agent payment rail.”

Time the presentation and remove any step that requires manual recovery.

---

## 3:50–4:00 — Freeze and capture

At 3:50:

* No new features.
* No refactoring.
* No dependency upgrades.
* No schema or field renaming.
* Fix only demo-blocking failures.

Create:

```bash
git tag demo-final
```

Keep the application running and capture screenshots of:

* Band coordination
* Actian memory retrieval
* Initial and improved rankings
* Pioneer job or evaluation status
* cited.md output
* x402 response or demo mode

---

# Git workflow that avoids collisions

Use three branches:

```text
main
intelligence
product
```

Person 1 works only on:

```bash
git checkout intelligence
```

Person 2 works only on:

```bash
git checkout product
```

At checkpoints, merge both into `main` together.

```bash
git checkout main
git merge intelligence
git merge product
```

After every integration checkpoint:

```bash
git checkout intelligence
git merge main

git checkout product
git merge main
```

Do not leave merging until 3:30 p.m. That is how hackathons accidentally become conflict-resolution seminars.

---

# Communication protocol

Use short status messages every 30 minutes:

```text
DONE:
- Pioneer extraction returns Event schema.

NEXT:
- Connecting Actian retrieval.

BLOCKED:
- None.

CONTRACT CHANGES:
- None.
```

When one person needs a contract change:

```text
PROPOSED CONTRACT CHANGE:
Add “confidence” to Recommendation.

REASON:
Needed to display uncertainty.

BREAKING:
No, optional field.
```

The other person acknowledges before it is merged.

---

# Minimum viable submission

By 4:00 p.m., the project must demonstrate:

* A user specifies networking, knowledge and opportunity goals.
* Agents discover or ingest multiple types of events.
* Pioneer structures or evaluates the events.
* Actian retrieves previous outcomes.
* Band coordinates specialized agents.
* The system recommends an event.
* It creates an actionable attendance mission.
* It publishes grounded output to cited.md.
* It exposes a paid output through an agent payment rail.
* Post-event feedback changes the next recommendation.

Everything else is decoration. The winning moment is the screen where the judges see the ranking **change for an evidence-based reason**.
