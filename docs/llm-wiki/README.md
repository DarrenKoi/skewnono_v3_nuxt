# LLM Wiki Research and Company Setup Guide

Researched: 2026-04-28

## Summary

An LLM Wiki is a persistent, LLM-maintained knowledge base. Instead of using only
retrieval augmented generation (RAG), where the model retrieves raw chunks every
time a question is asked, an LLM Wiki compiles source material into durable,
cross-linked Markdown pages.

For company projects, the best practical setup is a hybrid:

1. Use an LLM Wiki for durable project memory.
2. Use RAG or search for raw-source lookup.
3. Use Git and pull request review before generated wiki updates become official.

Do not put confidential company data into a public hosted demo. Start with a
local or self-hosted workflow.

## What LLM Wiki Means

The LLM Wiki pattern was described by Andrej Karpathy as a way to build a
personal or team knowledge base with three layers:

| Layer | Purpose |
| --- | --- |
| Raw sources | Immutable source material such as specs, notes, transcripts, tickets, and documents. |
| Wiki | LLM-generated Markdown pages with summaries, concepts, entities, decisions, and cross-links. |
| Schema | Instructions that define how the LLM should ingest, query, cite, update, and lint the wiki. |

The main difference from plain RAG is that the synthesis is stored and improved
over time. Each ingest can update multiple wiki pages, add links, flag
contradictions, and keep project knowledge current.

## Core Operations

### Ingest

The LLM reads one or more raw sources, extracts the important information, and
updates the wiki.

Expected ingest outputs:

- Source summary page
- Updates to existing component, concept, decision, or runbook pages
- New pages when needed
- Updated `wiki/index.md`
- Updated `wiki/log.md`
- Citations back to raw source files
- Open questions or contradictions

### Query

The LLM answers questions from the compiled wiki first, then uses raw sources or
search when the wiki is incomplete.

Good answers should be saved back into the wiki when they create durable project
knowledge.

### Lint

The LLM periodically checks wiki health.

Lint should look for:

- Stale claims
- Contradictions between pages or sources
- Missing source links
- Orphan pages
- Broken cross-links
- Important concepts without canonical pages
- Data gaps that need more source material

## Recommended Company Setup

Create one LLM Wiki per active project or product area. Keep it inside the
project repository when possible, because Git provides history, review, and
rollback.

Recommended folder structure:

```text
docs/llm-wiki/
  WIKI_SCHEMA.md
  raw/
    specs/
    meetings/
    decisions/
    incidents/
    tickets/
    architecture/
  wiki/
    index.md
    log.md
    overview.md
    components/
    concepts/
    decisions/
    runbooks/
    sources/
```

For this notes repository, the guide itself starts in:

```text
llm-wiki/
  README.md
```

## First Pilot Plan

Start with one currently active company project.

1. Create `docs/llm-wiki/` inside the project repository.
2. Add `WIKI_SCHEMA.md` with project-specific rules.
3. Add 5 to 10 trusted raw sources:
   - `README.md`
   - architecture docs
   - deployment docs
   - API specs
   - database schema notes
   - major design decisions
   - release notes
   - incident reports
   - summarized meeting notes
   - important Jira, Linear, or GitHub issues
4. Ask the LLM to ingest one source at a time.
5. Review generated changes before committing.
6. Run a weekly lint pass.

## Suggested `WIKI_SCHEMA.md` Rules

Use a schema file to keep the LLM disciplined.

Minimum rules:

- Raw sources are immutable. Never rewrite files under `raw/`.
- The wiki is LLM-maintained but human-reviewed.
- Every non-trivial claim must cite a raw source path or URL.
- Unverified claims must be marked as `Unverified`.
- Conflicting claims must be marked as `Conflict`.
- Do not include secrets, credentials, tokens, private keys, or customer PII.
- Update `wiki/index.md` after every ingest.
- Append an entry to `wiki/log.md` after every ingest, query saved as a page, or lint pass.
- Prefer small, focused pages over large catch-all documents.
- Use relative links between wiki pages.
- Open a pull request for review before generated wiki updates become official.

Example log format:

```markdown
## [2026-04-28] ingest | Deployment README

- Added `wiki/runbooks/deployment.md`
- Updated `wiki/components/backend-api.md`
- Found one open question about staging rollback ownership
```

## Tooling Options

### Markdown, Git, and Codex or Claude Code

This is the lowest-friction option for engineering teams.

Best for:

- Project teams already using Git
- Engineering documentation
- Architecture and decision memory
- Reviewable knowledge updates

Tradeoffs:

- No built-in web UI unless you use Obsidian, MkDocs, Docusaurus, or another renderer
- Access control follows repository permissions
- Search starts simple unless you add a search tool later

### Open Source LLM Wiki App

The `lucasastorian/llmwiki` project is an open-source implementation of the LLM
Wiki pattern. Its README describes a stack with Next.js, FastAPI, Supabase,
S3-compatible storage, and an MCP server for Claude.

Best for:

- Teams that want a web UI
- Uploaded documents
- MCP-based LLM operation
- Source viewing and wiki rendering

Tradeoffs:

- More infrastructure than a simple Markdown folder
- Needs Supabase and S3-compatible storage
- Should be security-reviewed before company use

### Onyx

Onyx is a broader enterprise knowledge assistant with connectors and RAG
infrastructure. It is useful when the company needs to index systems such as
GitHub, GitLab, Confluence, Jira, Slack, Google Drive, SharePoint, Notion, and
other sources.

Best for:

- Many source systems
- Organization-wide search/chat
- Connector-based sync
- Permission-aware enterprise setups

Tradeoffs:

- More operational complexity
- Full permission sync can require enterprise features
- It is closer to enterprise RAG than pure LLM Wiki

### Open WebUI Knowledge

Open WebUI provides knowledge bases where teams can upload project docs and
attach them to models. It supports focused retrieval and full-context modes.

Best for:

- Lightweight internal document chat
- Fast local or self-hosted experiments
- Teams already using Open WebUI

Tradeoffs:

- More RAG-centered than LLM Wiki-centered
- Native function calling changes how knowledge is used
- Needs process discipline if you want durable wiki pages

### Custom RAG or File Search

Use OpenAI Retrieval/File Search, LangChain, or LlamaIndex when you need to
embed retrieval into a product or internal portal.

Best for:

- Custom apps
- Product-integrated assistants
- Structured permissions and workflows
- Programmatic ingestion

Tradeoffs:

- Requires engineering time
- You must design source ingestion, permissions, evaluation, and observability
- It will not become an LLM Wiki unless you also persist synthesized pages

## Security and Governance Rules

For company use, make these rules non-negotiable:

- Keep raw sources immutable.
- Keep generated wiki pages in Git or another versioned system.
- Require human review for generated changes.
- Separate wikis by project and access boundary.
- Do not ingest secrets, credentials, private customer data, or unrestricted chat exports.
- Prefer summarized meeting notes over raw meeting transcripts when sensitive content may appear.
- Require citations for all operationally important claims.
- Mark uncertainty clearly.
- Add owners for key pages such as deployment, incident response, and architecture overview.
- Run periodic lint checks.

## Practical Starting Commands

Inside a company project repository:

```bash
mkdir -p docs/llm-wiki/raw/{specs,meetings,decisions,incidents,tickets,architecture}
mkdir -p docs/llm-wiki/wiki/{components,concepts,decisions,runbooks,sources}
touch docs/llm-wiki/WIKI_SCHEMA.md
touch docs/llm-wiki/wiki/index.md
touch docs/llm-wiki/wiki/log.md
touch docs/llm-wiki/wiki/overview.md
```

Then ask the LLM:

```text
Use docs/llm-wiki/WIKI_SCHEMA.md as your operating rules.
Ingest docs/llm-wiki/raw/specs/<source-file>.
Update the wiki pages, index, and log.
Do not modify raw sources.
Mark uncertain claims and cite source paths.
```

## Evaluation Checklist

Before rolling out beyond the pilot project, verify:

- Can a new engineer understand the project from `wiki/overview.md`?
- Are major components documented?
- Are major architectural decisions documented?
- Can the wiki answer common onboarding questions?
- Are claims cited?
- Are secrets excluded?
- Are stale or contradictory pages flagged?
- Does the review process catch bad LLM edits?
- Is the maintenance cost lower than the old documentation workflow?

## Sources

- Andrej Karpathy, LLM Wiki pattern:
  <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- Open-source LLM Wiki implementation:
  <https://github.com/lucasastorian/llmwiki>
- LLM Wiki README:
  <https://raw.githubusercontent.com/lucasastorian/llmwiki/master/README.md>
- Onyx deployment docs:
  <https://docs.onyx.app/deployment/local/docker>
- Onyx connectors overview:
  <https://docs.onyx.app/admins/connectors/overview>
- Open WebUI Knowledge docs:
  <https://docs.openwebui.com/features/workspace/knowledge/>
- OpenAI Retrieval docs:
  <https://platform.openai.com/docs/guides/retrieval>
- LangChain Retrieval docs:
  <https://docs.langchain.com/oss/javascript/langchain/retrieval>
