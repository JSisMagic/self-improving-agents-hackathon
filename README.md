# Event Copilot

Event Copilot is a self-improving event-recommendation agent. It helps a user
choose events for networking, knowledge, and opportunity outcomes; creates a
measurable attendance mission; publishes grounded output; and learns from
post-event feedback so later rankings improve.

The repository is currently in a time-boxed hackathon build. The active specs
define only the vertical slice needed for the demo; detailed post-hackathon
design work is preserved in a non-normative archive.

## Start here

- [Quick two-person build plan](QUICK-PLAN.md)
- [Specification system](specs/README.md)
- [Repository guidance](AGENTS.md)
- [Specification catalog](specs/00-governance/catalog.md)
- [Product requirements](specs/01-product/PRD-001-event-copilot.md)
- [Demo workflow](specs/05-workflows/WFL-001-demo-journey.md)
- [Delivery plan](specs/08-delivery/DEL-001-hackathon-delivery.md)
- [Acceptance checks](specs/08-delivery/TST-001-acceptance-plan.md)
- [Requirement traceability](specs/00-governance/traceability.md)

## Source of truth

Accepted specifications and accepted architecture decision records listed as
active in the catalog are normative. Documents under `specs/archive/` and the
original planning documents remain useful design history, but they do not
override active specs:

- [Challenge statement](task.md)
- [Contract-lock notes](step1.md)
- [Two-person build plan](work-divide.md)

When implementation and an accepted spec disagree, either change the
implementation or accept a spec/ADR change before treating the divergence as
intentional.

## Run the browser demo

Start the dependency-free browser GUI:

```bash
PAYMENTS_ENABLED=false python3 -m product.ui --browser
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). Enter a profile and
three events, or select **Fill example** to populate every editable field with
the canonical demo data. The feedback step is editable too. Select **Run full
demo** for the complete canonical journey. After feedback, the app removes the
attended event and ranks a fresh slate containing a newly grounded live event.
The default app keeps episode memory only for the current server session.
Connected Actian mode persists it in VectorAI DB and reports
`storage_mode: live`.

## Run with real Band collaboration

Connected mode uses four independently authenticated Band remote agents:
Coordinator, Scout, Analyst, and Coach. The Coordinator creates one room per
recommendation run and recruits the specialists. Targeted messages move the
work through Coordinator → Scout → Analyst → Coach → Coordinator while Band
provides identity, room membership, WebSocket delivery, processing state, and
the inspectable transcript. The specialists still call the app's deterministic
validation, ranking, critique, and mission functions.

1. Under the same Band owner, create four **External Agent** records so they
   are sibling agents the Coordinator can recruit. Retain each one-time API key
   plus Agent UUID.
2. Install the optional Band runtime:

   ```bash
   python3 -m pip install -r requirements-band.txt
   ```

3. Copy `.env.example` to `.env`, set the four Agent UUID/key pairs, and change
   `BAND_ENABLED=true`. Export it before starting the app:

   ```bash
   set -a
   source .env
   set +a
   PAYMENTS_ENABLED=false python3 -m product.ui --browser
   ```

The initial recommendation screen shows the actual Band mode, room ID, and
sanitized message provenance. A connected claim is made only after the
Coordinator receives Coach's completion through Band. If Band is disabled,
misconfigured, unavailable, or times out, the same role functions execute
directly and the UI displays `demo_fallback`.

## Run with Actian semantic memory

Actian VectorAI DB is the connected EventEpisode store and semantic retrieval
layer. The app embeds stable Event features locally, stores the complete
schema-valid episode as Actian payload, and filters every search by `user_id`
and `schema_version`. The deterministic JSON backend remains the automatic
fallback.

1. Install the optional Python profile:

   ```bash
   python3 -m pip install -r requirements-actian.txt
   ```

2. Start VectorAI DB:

   ```bash
   docker compose -f compose.actian.yml up -d
   ```

3. Copy `.env.example` to `.env`, set
   `ACTIAN_VECTORAI_ENABLED=true`, and export the configuration:

   ```bash
   set -a
   source .env
   set +a
   PAYMENTS_ENABLED=false python3 -m product.ui --browser
   ```

The first model load may populate the local Hugging Face cache. A connected
feedback write uses `storage_mode: live`; missing dependencies, model files,
health, or provider operations use `local_fallback` without exposing provider
details. Run `ACTIAN_VECTORAI_ENABLED=true python3 -m intelligence.demo` for a
focused write-and-retrieve smoke check.

## Run the terminal vertical slice

The dependency-free terminal view exercises Hasan's six demo controls with
session-local episode storage by default. It never publishes or initiates a
payment on the default path:

```bash
PAYMENTS_ENABLED=false python3 -m product.ui --all
```

Run the full local verification suite with:

```bash
python3 scripts/validate_specs.py
python3 -m unittest discover -s tests -v
```

The default run reports episode storage as `local_fallback`, Band and cited.md
as fallback/disabled, and x402 as `disabled`. A connected final run requires a
healthy Actian instance, Band credentials, explicitly injected cited.md and
x402 testnet adapters, and inspectable provider evidence.
