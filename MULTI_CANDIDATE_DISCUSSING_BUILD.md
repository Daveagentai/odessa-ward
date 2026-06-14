# Multi-Candidate "Discussing" Build — Summary

**Date:** 2026-06-14
**Branch:** gh-pages
**Bundle:** `assets/index-CDdqaBQN.js` (~853 KB)

## What changed

A new `Discussing` status was added to `calling_assignments` so multiple candidates can be considered before a single one is formally Proposed. Several supporting flows were built around it.

## Schema migrations applied to Supabase (project `tmoxwjrivsapriooddqe`)

```sql
ALTER TABLE calling_assignments ADD COLUMN IF NOT EXISTS released_at  timestamptz NULL;
ALTER TABLE calling_assignments ADD COLUMN IF NOT EXISTS released_by  uuid        NULL
  REFERENCES profiles(id) ON DELETE SET NULL;
```

`member_id` was already nullable. `status` is a free-form `text`, so the new `"Discussing"` value needs no enum migration. The pre-existing `released_date` column is preserved for backward compatibility.

## UI changes (all in `index-CDdqaBQN.js`)

### Calling Queue page (xA)
- New violet `Discussing` filter chip (leftmost) and color in the status map.
- Bishopric-only header button opens the **Discuss / Propose Calling** dialog. Two-stage flow: pick an existing calling or create a new master entry; then either "Save as Discussing" or "Propose to a Member" with member picker.
- Per-row filter: when viewer.role = `org_president` AND calling_name ∈ {Relief Society President, Elders Quorum President, Sunday School President, Young Women President, Primary President} AND calling.organization = viewer.org, the row is hidden.

### Calling Detail page (yA)
- When `D.status === "Discussing"`: shows **Propose Candidates / Withdraw / Archive** actions.
- Propose-Candidates dialog has a member picker that loads members in real time, and on submit copies any `proposed_notes` into general `notes` with a "From proposal (Mon DD YYYY):" header.
- New **Revert to Discussing** button (violet) shown when status ∈ {Proposed, On Hold, Withdrawn, Approved, Declined, Extended, Accepted}. Confirm dialog clears `member_id`, `household_id`, all interview fields, proposal fields, approval/extension/acceptance/decline/withdrawn fields, and sets `status = "Discussing"`. The general `notes` field is preserved.
- **Set Apart auto-prompt:** when `releasing_member_id` is non-null, clicking "Mark Set Apart" opens a prompt: "Also release the previous holder?". Options:
  - **Yes, Set Apart and Release** — sets this row to Set Apart AND updates the releasing member's Active assignment to `Released` (with `released_at`, `released_by`, `released_date` populated).
  - **Set Apart Only (release later)** — just marks Set Apart.
  - **Cancel**.
- All `status = "Released"` paths (Complete Release on Pending Release, direct Release on Active) now populate the new `released_at` and `released_by` columns in addition to `released_date`.

### Callings Directory / Active list (dA)
- Per-holder row now has a new violet **Release & Discuss** button next to **Release & Propose**. It opens a confirm dialog with optional notes; on submit creates a new `calling_assignments` row with:
  - `status = "Discussing"`
  - `releasing_member_id = current holder.member_id`
  - `releasing_member_name = current holder's full_name`
  - `notes = (optional)` from the dialog
- The current holder remains Active until a replacement is set apart (handled by the Set Apart prompt above).
- The pre-existing Release dialog's `dn` mutation now also populates `released_at`, `released_by`, and `updated_at` when the user chooses "Release Now".

### Clerk Report (bA)
- The Releases section was already in place and continues to read from the `releases-report` query. With the new mutations it will now include `released_at` audit metadata on every entry.

## Commits

```
ed9fd70  Full data backup 2026-06-14 (pre-Discussing build)
e21edeb  Document released_at/released_by migration applied 2026-06-14
4e0f993  Queue: add Discussing filter chip + Discuss/Propose Calling dialog
a1643d6  Detail: Discussing-state actions + Propose Candidates dialog
02bbf7a  Detail: Revert to Discussing button + confirm dialog
16ae8e7  Callings list: add Release & Discuss button + dialog
04ccc96  Detail: Set Apart auto-prompt when releasing_member_id is set
cb84749  Releases: populate released_at and released_by on every release path
20a3a8d  Queue: hide president-replacement rows from the relevant org president
```

## Verification

```
braces:   0  (balanced)
brackets: 1  (matches pre-build baseline)
parens:   0  (balanced)
node --check: OK
```

## Backups

Full pre-build snapshot of every table is at `backup/2026-06-14/` (18 files, 1,830 rows total across all tables; see `data_*.json` and `schema_*.json`). The members CSV / migration documentation in `tools/lcr_import/` is untouched.
