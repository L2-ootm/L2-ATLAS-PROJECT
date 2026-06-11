# Diverse Efficient Agent Memory Framework

Date: 2026-06-08
Status: Conceptual input document. The canonical memory framework spec is `AGENT_MEMORY_FRAMEWORK_STRATEGY.md` (**6 layers** — the 7-item candidate list below counts OpenGraph and Graphify separately; D-021 §3 consolidates them into Layer 4 Graph Memory). Where this doc and the strategy doc differ, the strategy doc wins.

## Principle

A major differentiator for the L2/ATLAS harness should be memory architecture.

Most current agent harnesses treat memory as one of:

- chat history;
- simple vector search;
- profile notes;
- static RAG documents;
- isolated project files.

ATLAS should instead combine multiple memory modes into a governed, efficient, agent-native memory framework.

## Target direction

```text
Durable facts + semantic retrieval + graph relationships + compiled wiki + audit/event memory + skill memory
```

This should be built as part of the evolved Hermes/L2 foundation, not as a random add-on.

## Candidate memory layers

### 1. Hermes memory and session search

Purpose:

- user profile;
- persistent preferences;
- session recall;
- stable operational facts;
- self-improving skill extraction.

ATLAS role:

- preserve Hermes memory strengths;
- add stricter memory classification;
- prevent stale task artifacts from becoming long-term memory;
- connect memory writes to audit and source provenance.

### 2. LLM Wiki compiled knowledge

Purpose:

- curated project/source knowledge;
- maintained wiki pages;
- citations and source registry;
- index/log/lint model;
- contradiction and stale-claim detection.

ATLAS role:

- long-term operating knowledge;
- research synthesis;
- evidence-grade documentation;
- project/company memory that agents can update safely.

### 3. Turbovec / compact local semantic retrieval

Purpose:

- efficient local vector retrieval;
- fast semantic candidate search;
- privacy-preserving local index;
- no mandatory cloud vector DB.

ATLAS role:

- optional semantic layer over SQLite/BM25/FTS metadata;
- benchmarked against real ATLAS queries;
- fallback to FTS if unavailable;
- source IDs must stay stable across rebuilds.

### 4. OpenGraph / graph memory

Purpose:

- relationship-aware memory;
- entities, people, projects, missions, sources, decisions, providers, skills, artifacts;
- traversable context, not just nearest-neighbor chunks.

ATLAS role:

- model operational relationships;
- connect missions to runs, artifacts, decisions, people, skills, sources, and outcomes;
- support questions like “what decisions led here?”, “which skills are tied to this workflow?”, “who/what is connected to this opportunity?”

### 5. Graphify memory

Purpose:

- transform project/docs/code/conversation structures into queryable graph representations;
- keep architecture and project state navigable;
- extract relationships across sources.

ATLAS role:

- project knowledge graph;
- dependency/decision maps;
- memory graph maintenance;
- graph-aware context assembly for agents.

### 6. Audit/event memory

Purpose:

- every meaningful action has durable event records;
- tool calls, model calls, approvals, failures, artifacts, and state transitions become queryable.

ATLAS role:

- operational memory;
- run replay;
- accountability;
- provenance for memory updates;
- evidence for future planning/research.

### 7. Skill/procedure memory

Purpose:

- reusable workflows;
- procedures learned from difficult tasks;
- operational playbooks.

ATLAS role:

- L2-curated skill packs;
- skill classification;
- skill provenance;
- skill effectiveness tracking;
- safe sharing/export.

## Memory router concept

ATLAS should not expose all memory to every agent at all times.

It needs a memory router:

```text
task intent + policy + sensitivity + source scope -> selected memory layers -> compressed context package
```

The router should decide:

- whether to use profile memory;
- whether to search session history;
- whether to query wiki;
- whether to use semantic retrieval;
- whether to traverse graph memory;
- whether to load skills;
- whether to inspect audit trails;
- whether memory is safe to inject into the current model/provider.

## Required controls

- Memory writes need provenance.
- Sensitive memory requires policy labels.
- External/untrusted sources must be marked.
- Vector retrieval cannot replace citations.
- Graph relationships must not become hallucinated facts without source backing.
- Memory should be compact and efficient, not context bloat.
- Local/private memory should stay local by default.
- Agent memory should be queryable, inspectable, and correctable by the operator.

## Phase impact

### Phase 4.5

Add this as a differentiator in foundation/capability strategy.

### Phase 6

Phase 6 should not be just “wiki runtime.” It should be reframed as the first implementation step of the broader ATLAS memory framework:

- wiki/source registry;
- FTS/search;
- optional semantic retrieval path;
- memory provenance;
- graph-memory research input;
- audit-linked memory updates.

### Phase 8

Cockpit needs a memory surface:

- source browser;
- wiki browser;
- graph view later;
- memory inspection/correction;
- retrieval diagnostics;
- “why was this context loaded?” visibility.

## Strategic differentiator

The L2/ATLAS harness should be stronger than current agent harnesses because it combines:

```text
Hermes self-improving memory + LLM Wiki + local semantic retrieval + graph memory + audit provenance + skill memory
```

The goal is not more context. The goal is better selected, more trustworthy, more efficient memory.
