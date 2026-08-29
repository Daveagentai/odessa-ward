# Odessa Ward CRM — Design Document

**Version 2.0** · Last refreshed 2026-08-29

Start-here orientation for anyone new to this codebase (including future-me in a fresh session). Details live in the `docs/` folder; this document is the executive summary.

---

## What it is

A custom web app for a Latter-day Saint ward (church congregation) to run day-to-day bishopric and ward-council operations. It manages members, households, callings, visits, tasks, ministering assignments, and clerk workflows around LCR (Leader and Clerk Resources at lds.org) data. LCR is the source of truth for household roster/address data; the app pulls periodic XLSX exports from LCR into Supabase and lets clerks track the state LCR doesn't know about (engagement, callings, tasks, visits, pending contact-change reviews).

- **Live URL:** https://odessa-ward.dhoussian.workers.dev/
- **Repo (deployed bundle):** `Daveagentai/odessa-ward` branch `gh-pages`
- **DB:** Supabase project `tmoxwjrivsapriooddqe` (us-west-2, Postgres 17.6)
- **Version banner:** the bundle logs `Odessa Ward CRM 1.3.1` at startup.

## Who uses it

- **Bishop** (Dave — the primary user): manages the ward, sees everything, does most clerk work himself in this ward.
- **Bishopric counselors / clerks / secretary:** log visits, update statuses, run the Clerk Report.
- **Auxiliary leaders (RS/EQ/YW/YM presidents, ministering leaders, etc.):** limited views scoped by role.
- **Ordinary members:** no direct login by design. This is an internal operations tool.

## The critical operating rules (from the user)

Preserved verbatim from prior sessions. Everything else below is subordinate to these.

- **"Trust the report spreadsheet."** The LCR XLSX export is the source of truth for who is in the ward and what their household address is.
- **"We do not update names in the Ward CRM."** LCR is the source of truth for names.
- **"Non-members are called Friends."** UI language uses "Friends", not "non-members."
- **"Multiple households at the same address is FINE."** Don't dedupe on address.
- **"Please completely separate the Household Activity Status from the Family Status."** Household `activity_status` and member `lcr_status` are independent — no cascade, no clamp, no cross-write.
- **"There is no member status that comes from the LCR. Member status comes only from the app."** LCR importer must never write `members.lcr_status` on existing rows.
- **"New member earned insert gets the status of Unknown."** Both new-household and new-member INSERTs default to Unknown.
- **"Document everything you learn as we're working here please."** This document, `docs/`, the `capture-learnings` and `lcr-import` skills, and the `memory/` wiki are all instances of that rule.
- **"When you go to commit code, make sure you're writing it to both the repos and the gh-pages so that all the code stays in sync."** In practice for this project: gh-pages is the only live repo. `Daveagentai/ward-crm` is 5+ months stale and does not represent what's deployed — see "Source situation" below.

## Architecture at a glance

- **Frontend:** Vite + React SPA, Tailwind CSS, shadcn/ui + Radix primitives, wouter router, TanStack React Query, react-hook-form, lucide-react icons, DM Sans (Google Fonts). 17 routes, ~50 React Query keys. Deployed as a static bundle.
- **Backend:** Supabase (PostgreSQL 17.6). Auth via Supabase Auth (email/password). Row-Level Security enabled on all tables except `ministering_assignments`. Client hits Supabase directly via `@supabase/supabase-js` with the anon key. **Note:** the `service_role` JWT is currently on the client — moving it to a Worker/edge route is a known outstanding item.
- **Hosting:** Cloudflare Workers static-asset serving. `wrangler.jsonc` at repo root declares a Worker named `odessa-ward` with `assets.directory = "."` — the whole gh-pages branch is served as static assets. See `docs/deploy.md`.
- **Rich text:** Tiptap sidecar bundle (`assets/tiptap-bundle.js`, ~532 KB) for the member notes editor.
- **Map view:** Leaflet code-split into `assets/household-map-*.js` (~194 KB), lazy-loaded when the `/household-map` route is opened.

For deep dive, read `docs/architecture.md`.

## Data model at a glance

12 public tables in Supabase:

| Table | Purpose | Rows (2026-08-29) |
|-------|---------|-------------------|
| `members` | Every person LCR knows about + Friends | 601 (600 active + 1 friend) |
| `households` | Family groupings | 346 |
| `calling_assignments` | Who holds what calling; workflow state | 198 |
| `callings` | Master catalog of positions (orgs, roles) | 97 |
| `ministering_assignments` | Ministering brother/sister pairings | 274 |
| `visits` | Ministering / bishopric visit records | 32 |
| `tasks` | Bishopric/clerk task list | 20 |
| `profiles` | App users (14 people with logins) | 14 |
| `member_contact_changes` | Pending contact-change reviews awaiting LCR sync | 6 |
| `visit_attendees` | Multi-attendee visit records | (in use) |
| `bishop_notes` | Private bishop notes on a member | (in use) |
| `leadership_notes` | Auxiliary-leader notes on a member | (in use) |

Row counts drift with imports and clerk activity — treat as approximate. See `docs/architecture.md` for column-level detail and React Query keys.

## Status model (must read)

The most-discussed design area, and the most frequently re-derived. Household `activity_status` and member `lcr_status` are **fully independent**:

- **Household `activity_status`** — TEXT column, CHECK constraint, 8 values: `Active`, `Less Active`, `Not Active`, `Unknown`, `Do NOT Contact`, `Do NOT Contact - Hostile`, `Moved Out`, `Check for Moved Out`. The first 7 are clerk-facing. `Check for Moved Out` is importer-set only, awaiting clerk review.
- **Member `lcr_status`** — PostgreSQL enum `member_lcr_status`, 15 values. All 15 are clerk-facing. See `docs/status-model.md` for the full table.
- **Who writes what:** the LCR importer syncs households (address refresh + missing → `Check for Moved Out`). It never touches `members.lcr_status` on existing rows. It seeds `lcr_status='unknown'` on new-from-LCR inserts. From there, only clerks change member status.

For full detail, migration history, and rendering rules, read `docs/status-model.md`.

## LCR import workflow (must read)

Weekly-ish. XLSX (or Google Sheet tab) → deterministic SQL → chunked upload → verify → merge duplicates → clerk-review flagged households. Two-pass name matcher (original_full_name → preferred_name + household). Terminal statuses excluded from moveout candidates. Chunk staging table (`_lcr_import_staging`) to work around Supabase connector's query size limit.

For the operational routine, read the `lcr-import` skill and `docs/importer.md`.

## Source situation (important)

**The compiled bundle is our source of truth.** The React/TypeScript source that produced `assets/index-CDdqaBQN.js` is no longer available:

- `Daveagentai/ward-crm` (intended source repo) is 5+ months stale.
- All development since April 2026 has happened in ephemeral Perplexity sandbox sessions that generated source, compiled it, pushed the bundle to `Daveagentai/odessa-ward` gh-pages, and let the sandbox evaporate.
- **All app-behavior changes today happen by regex-patching the minified bundle** and pushing directly to gh-pages.

Reverse-engineering the bundle back into a buildable source tree is a known outstanding item — see "Roadmap" below.

**How we live with this:**

- `docs/bundle-identifiers.md` is the durable map of minified names (`VO`, `eA`, `oA`, `Ue`, `Ne`, etc.) to real names, so we don't re-derive them each session.
- `docs/bundle-patches.md` is the chronological log of every hand-patch: what changed, at what offset, and why.
- Bundle-patch workflow enforces: single unique anchor before replace; balance check `(-1, 0, 1)`; `node --check` passes; cache-buster (`?v=YYYY-MM-DD-N`) bumped on `index.html`.
- The bundle filename `assets/index-CDdqaBQN.js` **never changes** across in-place patches — that's why the cache buster on the script tag matters.

## Roadmap (outstanding items)

Roughly in priority order.

- **Reconstruct a buildable source tree from the compiled bundle.** Biggest deferred item. Would allow real feature work instead of surgical bundle patches.
- **Move the `service_role` JWT off the client** into a Worker/edge route. Security item — currently the client can perform privileged writes.
- **Move the LCR importer to run inside the app** instead of via the local Python CLI (`tools/lcr_import/import.py`). Would let non-Dave clerks run imports.
- **Auto-detect stale households and members** at import time with more nuance (currently household-only auto-flag; individually-missing members surface on the Clerk Report but are never auto-flagged).
- **Ministering assignment RLS.** Only table without RLS today.
- **Full-text search** for the member/household directory (current search is per-column, non-fuzzy).

## Where things live

```
odessa-ward-app/                       ← local clone of Daveagentai/odessa-ward gh-pages
├── DESIGN_DOCUMENT.md                 ← this file
├── README.md                          ← thin repo README
├── index.html                         ← HTML shell + cache-busted <script>
├── wrangler.jsonc                     ← Cloudflare Worker config
├── assets/
│   ├── index-CDdqaBQN.js              ← MAIN BUNDLE (~897 KB), patched in place
│   ├── index-x69SfmxN.css             ← Tailwind + custom CSS
│   ├── household-map-3WNoBbc8.js      ← code-split map bundle
│   ├── tiptap-bundle.js               ← rich-text editor sidecar
│   └── tiptap-bundle.css
├── docs/                              ← durable knowledge; READ FIRST when starting work
│   ├── README.md                      ← index / policy for this folder
│   ├── architecture.md                ← routes, tables, hooks, dependencies
│   ├── status-model.md                ← the 8+15 status model, migration history
│   ├── deploy.md                      ← Cloudflare Worker deploy pipeline
│   ├── importer.md                    ← LCR importer behavior + invariants
│   ├── bundle-identifiers.md          ← minified-name → real-name map
│   └── bundle-patches.md              ← chronological patch log
├── tools/
│   └── lcr_import/
│       └── import.py                  ← LCR import script (Python + openpyxl)
├── tiptap-sidecar/                    ← separate sub-project for Tiptap bundle
└── backup/                            ← legacy DESIGN_DOCUMENT.md snapshots (Apr–May 2026, superseded)
```

## Related resources

- **User skills** (Perplexity sandbox scope): `lcr-import` (import routine), `capture-learnings` (meta-skill for making fixes stick).
- **Memory wiki:** `memory/knowledge/projects/odessa-ward-crm.md` — high-level facts about this project.
- **This document + `docs/`** are the durable, in-repo record. Everything critical must land here, not just in memory or a skill.

## Last verified

- 2026-08-29 — v2.0 rewrite. Consolidated the modular `docs/` files, filled in `deploy.md` and `importer.md`, refreshed row counts, folded in all changes since the May 3 2026 legacy DESIGN_DOCUMENT.md.
