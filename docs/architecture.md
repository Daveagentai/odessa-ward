# Architecture

## Deployed asset shape

The deployed app is a static single-page React bundle served from `Daveagentai/odessa-ward` `gh-pages`:

- `index.html` — HTML shell. Loads `assets/index-*.css` and imports `assets/index-*.js` as a module.
- `assets/index-CDdqaBQN.js` — 895 KB. Main bundle. All routes, most components, Supabase client, data hooks.
- `assets/index-x69SfmxN.css` — 121 KB. Tailwind + custom. Imports DM Sans from Google Fonts.
- `assets/household-map-3WNoBbc8.js` — 194 KB. Code-split bundle for the `/household-map` route (Leaflet + map view).
- `assets/tiptap-bundle.js` + `assets/tiptap-bundle.css` — 532 KB + 2 KB. Tiptap rich-text editor (sidecar; separate sub-project at `tiptap-sidecar/`).

## Serving path

`wrangler.jsonc` at repo root declares a Cloudflare Worker named `odessa-ward` with `assets.directory = "."` — the whole repo is served as static assets. Whether pushes auto-deploy or need a `wrangler deploy` step is not yet confirmed in this doc — see `deploy.md`.

## Routes (17)

```
/home                    — Home / dashboard
/directory               — Member Directory (list, search, filter)
/directory/:id           — Member detail
/household/:id           — Household detail
/callings                — Callings Directory
/calling-queue           — Kanban of proposed/discussing/extending/etc callings
/calling-detail/:id      — Single-calling drill-down
/tasks                   — Task list
/new-visit               — Log a visit
/visits-report           — Visits report
/search-members          — Advanced member search / filter
/search-household        — Advanced household search / filter
/household-map           — Map view of all households (code-split)
/clerk-report            — Clerk-facing status/discrepancy report
/profile                 — Current user profile
/admin                   — User management (bishopric only)
/update-password         — Password reset flow
```

## Supabase tables (accessed by bundle)

| Table | Sites | Notes |
|-------|-------|-------|
| `members` | 24 | Largest surface. Includes `lcr_status`, `original_full_name`, `preferred_name`, `household_id`, ministering, temple, contact fields. |
| `calling_assignments` | 21 | Calling workflow state, candidates, interview tracking. |
| `households` | 9 | Includes `activity_status`, `household_name`, address fields, `updated_at`. |
| `tasks` | 9 | Task management. |
| `visits` | 7 | Ministering / bishopric visits. |
| `callings` | 6 | Master calling catalog (orgs, positions). |
| `profiles` | 6 | Ward CRM app users. |
| `member_contact_changes` | 4 | Pending contact change reviews. |
| `visit_attendees` | 4 | Multi-attendee visits. |

## Data hooks (React Query keys, ~50)

Categorized by domain:

**Members / Households:**
`members`, `members-list`, `members-picker-all`, `member`, `member-callings`, `member-tasks`, `member-visits`, `all-members-for-tasks`, `search-members`, `search-household`, `household`, `households`, `household-name`, `household-members`, `household-members-list`, `household-member-counts`, `household-tasks`, `household-visits`, `friends-list`, `pending-contact-changes`, `pending-contact-changes-all`, `clerk-moveout-households`, `clerk-moveout-members`.

**Callings:**
`callings`, `callings-master-for-discuss`, `calling-detail`, `calling-queue`, `calling-reconciliation`, `active-assignments`, `board-candidate-members`, `board-members-namelist`, `candidate-members`, `member-callings`, `pending-interviews`, `interviewer-profiles`, `releases-report`, `set-aparts-report`, `sustainings-report`.

**Tasks / Visits:**
`tasks`, `my-tasks`, `home-tasks`, `member-tasks`, `household-tasks`, `all-users-for-tasks`, `visit-attendees`, `visits-report`, `recent-visits`, `member-visits`, `household-visits`.

**Users / Admin:**
`profile`, `all-profiles`, `all-profiles-visits`, `admin-users`, `active-users`, `bishopric-users`.

## Dependencies (inferred from bundle markers)

- React + react-dom (via `g` = React, `n` = jsx-runtime, `Sn` = flushSync)
- `@tanstack/react-query` (via `bt` = useMutation, `vr` = useQueryClient inferred, 69 hits)
- `@supabase/supabase-js` (via `createClient`, `.from(...).select(...)`, 139 hits)
- Routing: **wouter** (based on `Dr()` returning `[loc, setLoc]` tuple — wouter's `useLocation` API)
- shadcn/ui + Radix (Button, Card, Select, Checkbox, Dialog, etc.)
- lucide-react (icon factory `Ce("IconName", [...paths])`)
- react-hook-form (Controller, 8 hits)
- date-fns (formatDistance, formatRelative)
- Tailwind CSS + tailwind-merge (utility `He` merges classes)
- DM Sans font (via Google Fonts import at top of CSS)

## Version

Deployed bundle logs `Odessa Ward CRM 1.3.1` at startup (`console.log`).

## Last verified

- 2026-08-29 — captured during household-status-simplification bundle patch.
