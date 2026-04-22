# Odessa Ward CRM — Design Document

## Version 1.3 — Snapshot: April 21, 2026

---

## Overview

The Odessa Ward CRM is a custom-built web application for managing ward (church congregation) operations. It serves as a centralized tool for the bishopric and ward council to track members, households, callings, visits, tasks, and ministering assignments. LCR (Leader and Clerk Resources at lds.org) is the source of truth for member records; the app pulls periodic XLSX exports and pushes outgoing change requests via a Clerk Sync report.

## Architecture

### Frontend

- **Framework**: Vite + React (bundled as static SPA)
- **Styling**: Tailwind CSS
- **Hosting**: Cloudflare Workers (static site)
- **URL**: https://odessa-ward.dhoussian.workers.dev/
- **Source**: GitHub repo `Daveagentai/odessa-ward` (gh-pages branch)
- **Note**: All source exists ONLY as the bundled JS in `assets/index-CDdqaBQN.js`. Edits go in via careful string replacement.

### Backend

- **Database**: Supabase (PostgreSQL 17.6)
- **Project ID**: tmoxwjrivsapriooddqe
- **Region**: us-west-2
- **Auth**: Supabase Auth with email/password
- **RLS**: Row-Level Security enabled on all tables (except ministering_assignments)

---

## Database Schema

### Tables & Row Counts (as of April 21, 2026)

| Table | Rows | RLS |
|---|---|---|
| members | 568 | Yes |
| households | 324 | Yes |
| ministering_assignments | 274 | No |
| calling_assignments | ~150 | Yes |
| callings | ~83 | Yes |
| member_contact_changes | variable | Yes |
| tasks | variable | Yes |
| profiles | 12 | Yes |
| visits | variable | Yes |
| bishop_notes | variable | Yes |
| leadership_notes | variable | Yes |

### New Columns (added April 21, 2026)

**members**
- `original_full_name TEXT` — the true full name from LCR (e.g. "Adams, Dawson Lee")
- `lcr_status TEXT DEFAULT 'active'` — one of: `active`, `moved_out`, `deceased`, `name_removed`
- `lcr_last_seen_at TIMESTAMPTZ` — last time this member was seen in an LCR import

### New Table: member_contact_changes (April 21, 2026)
Tracks contact field edits (phone/email/address) made in the app that need to be typed back into LCR.
```
id, member_id, field_name, old_value, new_value,
changed_by, changed_at, synced_to_lcr, synced_at, synced_by
```
Shown on the Clerk Sync report under "Contact Updates". Auto-cleared when a subsequent LCR import has the new value.

### Name Display Invariant (new April 21, 2026)

Rather than editing 80+ display sites in the bundled JS, the app enforces a DB-side invariant:

- `original_full_name` = the true LCR full name (never displayed by default)
- `preferred_name` = what the person goes by (from LCR or hand-entered for Friends)
- `full_name` = **display name**: preferred_name if set, else original_full_name

A `BEFORE INSERT/UPDATE` trigger (`members_sync_full_name`) enforces the invariant automatically:
- On INSERT: backfills `original_full_name` from `full_name` if missing
- On UPDATE (e.g. during LCR import): captures the LCR-provided full_name into `original_full_name`, then overwrites `full_name` with `preferred_name` (or `original_full_name` as fallback)

The member detail page renders `original_full_name` as a small subtitle under the preferred name when the two differ. Every other display site (directory, search, member pickers, visit cards, task assignees, ministering lookups, etc.) just uses `.full_name` as before — and automatically gets the preferred name.

### Custom Enums

- **gender_type**: M, F
- **marital_status_type**: Married, Single, Divorced, Widowed
- **user_role**: bishop, bishopric, exec_sec, ward_clerk, rs_president, eq_president, org_president, ward_council
- **sensitivity_level**: bishop_only, leadership, bishopric, ward_council
- **task_priority**: Low, Medium, High, Urgent
- **task_status**: Not Started, In Progress, Completed, Abandoned
- **visit_type**: Home Visit, Phone Call, Text Message, In-Person Meeting, Email, Sacrament, Interview, Other

### Custom Functions

1. **get_my_role()** — Returns the current user's role from profiles
2. **admin_list_users()** — Bishop-only: lists all auth users with profiles
3. **admin_update_role()** — Bishop-only: updates a user's role
4. **admin_delete_user()** — Bishop-only: removes a user entirely
5. **members_sync_full_name()** (new April 21) — Trigger function enforcing the name display invariant

### RLS Policies on members (as of April 21, 2026)

- `members_all_read` — authenticated users can SELECT
- `members_insert` — authenticated users can INSERT
- `members_update` (added April 21) — authenticated users can UPDATE (fixes silent save failures on Friend edits and member contact edits)

---

## Features

### Member Directory
- 568 members with full LCR field coverage
- Search and filter by status/organization
- Multi-select filters (statuses, callings)
- Resizable and reorderable columns
- Individual member detail pages with all ~45 LCR fields
- Contact edit (phone/email/address) with automatic Clerk Sync tracking
- Preferred names used throughout the app (April 21)
- Directory hides members with lcr_status != active by default (deceased/moved out/name removal requested still searchable; visible on detail page with a badge)

### Friends (Non-Members)
- Any investigator, visitor, or non-member contact added to the app
- Full parity with member fields — can edit all ~40 LCR-style fields
- Preferred Name field available
- NOT included in the Clerk Sync report (no LCR counterpart)
- Visible in directory with amber "Friend" badge

### Household Management
- 324 households with addresses and geocoding (auto-lookup via Nominatim on edit)
- Household map view (Leaflet/OpenStreetMap)
- Activity status tracking (Active, Less-Active, Not Active, etc.)
- Emergency preparedness data

### Callings Directory & Workflow
**Status Flow**: Proposed → Approved → Extended → Accepted → Sustained → Set Apart → Active
**Additional statuses**: On Hold, Pending Release, Released, Declined, Withdrawn

**Workflow Features**:
- Propose members for callings with notes
- Approve/decline proposals
- Assign interviewers with "can_interview" flag on profiles
- Mark Extended/Accepted/Sustained/Set Apart
- Revert to Proposed button for Approved, Extended, and Accepted statuses
- Release with reason and date tracking
- On Hold with Resume & Propose / Resume & Approve options
- Release & Propose (replace) workflow
- Withdraw (declined) with queue filtering
- Clerk report with LCR reconciliation, type indicators, and dates
- Timeline and notes on calling detail pages

### Visit Notes
- Record visits by type (Home Visit, Phone Call, etc.)
- Sensitivity levels for privacy control (bishop_only, leadership, bishopric, ward_council)
- Follow-up tracking
- Permission levels (Bishop-only visits restricted)
- Calling Interview visit type includes member name in auto-generated title
- Visits filter fixed April 21: the YO component's `user?.id` references were throwing ReferenceError; now properly destructures `user` from the auth hook

### Task Management
- Create tasks linked to members/households
- Priority levels and due dates
- Assign to specific users or bishopric
- Organization-based filtering
- Permission level filtering

### Ministering Assignments
- Brothers and sisters assignments
- ~274 active assignments
- Linked to members and households

### LCR Sync (April 21, 2026 flow)
**Pull** (from LCR → App):
- User (clerk) exports XLSX from LCR manually (~quarterly)
- Drops file in chat; agent processes via `lcr_import_v2.py`
- Upserts households (unique by household_name) and members (unique by full_name)
- All LCR fields mapped; marital_status derived from is_married / is_widowed / is_divorced flags
- Members in DB not in export → classified as moved_out / deceased / name_removed (agent asks user)
- Pending contact_changes auto-cleared if LCR now matches

**Push** (from App → LCR):
- Clerk Sync report shows:
  - "Contact Updates" section: phone/email/address edits pending sync to LCR
  - Calling changes needing LCR entry
  - Mark-as-synced buttons on each
- Clerk (human) types changes into LCR, then marks as synced
- Friends are NOT included (no LCR counterpart)

### Access Control
**Roles with permission hierarchy (numeric)**:
1. Bishop (1) — Full access, admin functions
2. RS/EQ Presidents (2)
3. Bishopric, Executive Secretary, Ward Clerk (3)
4. Org Presidents (4)
5. Ward Council (5) — Basic access

**RLS Policies** enforce access control at the database level.

---

## Deployment

- Frontend builds via Vite → static assets in `assets/` directory
- Deployed to Cloudflare Workers via `wrangler.jsonc` config
- GitHub Pages branch (`gh-pages`) serves as deployment source
- Every change to `assets/index-CDdqaBQN.js` is pushed to GitHub with a commit message describing the fix/feature

## Authentication

- Bishop account: bishopdavehoussian@gmail.com
- Supabase Auth with email/password
- Session tokens via refresh_token flow
- `profiles.role` determines UI permissions and restricts destructive actions

---

## Change Log

### April 21, 2026 (this session)
- Fix: member visits/tasks not showing on detail page (YO component `user` destructure missing)
- Feature: Friend edit form expanded to full member field parity (~40 fields)
- Feature: member contact editing (phone/email/address) with automatic Clerk Sync tracking via `member_contact_changes` table
- Feature: Contact Updates section in Clerk Sync report with mark-as-synced
- Feature: amber "Contact Update Pending" badge on member detail page
- Fix: Calling Interview visit title now includes member name
- Fix: RLS UPDATE policy added to members table (silent save failures resolved)
- Feature: `lcr_status` column + moved_out / deceased / name_removed badges
- Feature: preferred-name-everywhere via DB trigger approach
- Feature: Full name subtitle on member detail page when different from preferred name
- Feature: Preferred Name field added to Friend edit form
- Feature: Directory hides non-active lcr_status by default
- DB import: 565 LCR records synced, 1 new insert (Tikhomirov), 3 flagged not-in-LCR (Duffy & Strite → deceased; Gross → moved out)

### April 20, 2026
- Friends feature basic + Friend edit mode + address + map integration

### April 19, 2026
- Withdrawn status, Withdraw button + queue filtering, Notes column, multi-select filters

### April 18, 2026
- Clickable member name, Confidential section role restriction

### April 13, 2026
- Resizable/reorderable columns, Releasing column

### April 12, 2026
- Restored workspace, baseline backup, pushed to GitHub (commit 1416f2b)
