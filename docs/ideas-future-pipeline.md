# Groundwork Ideas: Verification, Orchestration, and Live Status

Date: 2026-02-24  
Status: Brainstorm / not committed to implementation

## Context
Current concern: relying on a single LLM/search provider (Perplexity) is not enough for data integrity and trust.

## Product Direction (Draft)

### 1. Multi-source search + verification pipeline
Goal: move from single-pass generation to a verifiable, auditable intelligence pipeline.

High-level flow:
1. Kick off search across one or more providers (Perplexity + additional search API such as x.ai or equivalent).
2. Parse candidate sources and validate links (reachability, status code, content type, freshness).
3. Score each source by authority and relevance.
4. Build structured city transport intel from weighted evidence.
5. Route output to human review inbox before publish/final acceptance.

### 2. Source quality ranking model
Need explicit ranking logic so official sources dominate.

Potential ranking tiers:
- Tier A (highest trust): official transit authorities, city government transport pages, operator fare and service bulletins.
- Tier B: reputable news and partner organizations quoting official updates.
- Tier C: community forums and personal blogs (low trust, supporting evidence only).

Possible ranking signals:
- Domain authority class (official/public authority vs non-official).
- Publication/update recency.
- Presence of primary-source citations.
- Historical reliability score for source.
- Cross-source agreement/conflict signal.

### 3. Human-in-the-loop review inbox
Goal: all parsed/structured intel lands in a review queue before final acceptance.

Inbox item ideas:
- City + field-level extracted claims.
- Source links + ranking score + validation status.
- Diff vs previous accepted version (what changed).
- Reviewer actions: approve, reject, request re-run, flag uncertain.

### 4. Public feedback / correction channel
Goal: let users report inaccuracies quickly.

Example UX:
- "Tell us what is wrong on this page"
- "Fare changed from X to Y"
- "Link is broken"

Feedback pipeline concept:
1. Capture free-text feedback.
2. LLM structures into typed corrections (fare change, outage update, broken URL, etc.).
3. Validate against source checks.
4. Route to reviewer queue with confidence score.

### 5. Real-time-ish transit status as core feature
Ambition: normalized public transport status across cities (disruptions, engineering works, signal failures, etc.).

Conceptual requirements:
- Connector strategy per city/operator (e.g., TfL disruptions for London).
- Normalized status schema for incidents and service health.
- Polling cadence and staleness policy.
- Conflict handling when feeds disagree.
- Historical incident log for reliability and trend analysis.

### 6. Platform/API vision
Long-term direction:
- Expose Groundwork transport intelligence/status via API for external LLM agents.
- Make Groundwork data discoverable and attributable in downstream agent responses.

### 7. Groundwork-to-Potniq distribution model
Goal: maximize public utility and authority while still driving paid product growth.

Three-layer model:
- Layer 1 (Groundwork, free/public): city-level truth (fares, disruptions, service status) with citations and verification metadata.
- Layer 2 (Potniq Silver, paid after free itinerary allowance): route/trip-level decisioning ("what this means for my trip", best departure timing, route visualization).
- Layer 3 (Potniq Gold, future paid premium): proactive monitoring ("leave now", reroute alerts when conditions degrade).

Working principle:
- Groundwork answers "what is happening in this city?"
- Potniq answers "what should I do for my trip right now?"

### 8. SEO + agent distribution surface
Need both human pages and machine endpoints powered by the same accepted field-level truth.

Human SEO pages (examples):
- `/cities/new-york-city`
- `/cities/new-york-city/fares`
- `/cities/new-york-city/transit-modes`
- `/cities/new-york-city/disruptions`
- `/cities/new-york-city/fare-history`

Agent/API surfaces (examples):
- `/api/public/v1/cities/new-york-city/facts`
- `/api/public/v1/cities/new-york-city/fares`
- `/api/public/v1/cities/new-york-city/disruptions`
- `/api/public/v1/cities/new-york-city/changes?since=...`

Design requirement:
- Publish citations inline per field/fact (`source_url`, `publisher`, timestamps, excerpt, confidence).
- Keep JSON as canonical agent interface; optional markdown snapshots can be secondary for readability/RAG.

### 9. Intent-based CTA strategy
Core idea: CTA depends on user/agent intent context, not one static message.

Intent to CTA mapping:
- Discovery/planning intent (e.g., "best app for NYC travel"): route to Potniq planning CTA.
- Disruption impact intent (e.g., line closure, roadworks): route to Potniq route-impact CTA.
- Real-time/high-stakes intent (e.g., leave now decisions): route to Potniq monitoring CTA (Gold direction).

Example CTA families:
- Planning: "Traveling to Tokyo soon? Build a reliable itinerary in Potniq."
- Impact: "This disruption may affect your route. See route-specific alternatives in Potniq."
- Monitoring: "Enable monitoring so Potniq tells you when to leave."

### 10. Agent attribution and conversion mechanics
Constraint: generic agents cannot be forced to include links, so design for easy reuse and measurable attribution.

Include in API responses:
- `source_name` (e.g., "Groundwork by Potniq")
- `canonical_url` (Groundwork page)
- `action_url` (Potniq deep link with campaign/source params)
- `cta_primary` and optional `cta_alternatives` (label + intent)

Measurement:
- Track Groundwork page/API source to Potniq sessions and paid conversion.
- Keep top-value trip-specific decisioning in Potniq so high-intent integrations naturally depend on paid product surfaces.

## Architecture Tracks (Non-implementation notes)

Track A: Search abstraction layer
- Provider interface for multi-search fan-out and failover.
- Unified result object (url, title, snippet, provider, timestamp).

Track B: Validation + enrichment worker
- URL probing and content metadata extraction.
- Structured parser for fares, ticketing, and service status clues.

Track C: Ranking + evidence engine
- Weighted scoring model with explainable rationale.
- Evidence bundle attached to each extracted claim.

Track D: Review operations
- Inbox, reviewer workflow, and audit trail.
- Versioned acceptance state for city intel.

Track E: Community corrections
- Public feedback endpoint + moderation controls.
- Auto-triage into structured correction tasks.

Track F: Live status ingestion
- City/operator adapters.
- Normalization and freshness SLAs.

## Open Questions
- Which second search provider should be first (x.ai or another API)?
- Should publish be blocked until human approval for all cities, or only low-confidence changes?
- What freshness SLA is expected for live status per city tier?
- How should reviewer trust/reputation be handled if crowdsourcing is enabled?
- What attribution policy is needed so downstream agents cite Groundwork/Potniq consistently?
- What minimum public data is enough for authority without cannibalizing Potniq paid value?

## Suggested Next Step (Later)
Turn this into a phased RFC with:
- Schema changes.
- Queue/review data model.
- Provider adapter contract.
- Confidence + ranking rubric.
- Pilot city rollout plan.
