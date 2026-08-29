# LCR importer

Complements the `lcr-import` user skill. The skill is the operational routine (step-by-step how to run it); this doc is the design record (what it does, why, invariants).

## What it is

`tools/lcr_import/import.py` — a Python script that takes an LCR Bishop CRM Report XLSX (or a Google Sheets tab exported to XLSX shape) and produces a set of SQL files that, when executed against the Supabase database in order, sync the DB to the report.

**LCR is the source of truth** for:
- Who is in the ward (member roster).
- Household address / city / state / zip.
- Names (both `original_full_name` and `preferred_name`).
- Dates: birth, baptism, marriage, confirmation.
- Priesthood office, is-returned-missionary flag.

**LCR is NOT the source of truth** for:
- Member engagement state (`lcr_status`). That comes only from the app / clerk. The importer must never write `members.lcr_status` on existing rows.
- Callings, tasks, visits, ministering assignments, notes.

## What the importer produces

Running `python3 import.py <xlsx-path> <sheet-name>` writes these files to `/home/user/workspace/`:

| File | Purpose |
|------|---------|
| `lcr_import_households.sql` | Two-phase household sync: name-renames (matched by address if the household_name changed) then upsert (INSERT new with `activity_status='Unknown'`, ON CONFLICT DO UPDATE only refreshes address/city/state/zip; **never touches `activity_status` on existing households**). |
| `lcr_import_00_setup.sql` | Creates temp table `_lcr_import_staging (row jsonb)`. |
| `lcr_import_01_chunk_NN.sql` | 15–20 files, each ~50 KB, each doing `INSERT INTO _lcr_import_staging SELECT jsonb_array_elements($lcr$...$lcr$::jsonb)`. Chunked to fit under the Supabase connector's query-size limit. |
| `lcr_import_02_members.sql` | The small UPDATE + INSERT SQL that reads from `_lcr_import_staging`. Runs the two-pass matcher (see below). Returns `{updated_count, renamed_count, inserted_count}`. |
| `lcr_import_03_teardown.sql` | Drops the staging table. |
| `lcr_import_changed.sql` | Field-change audit (currently a no-op placeholder). |
| `lcr_import_presence.sql` | Bulk `lcr_last_seen_at = now()` ping for every LCR row. |
| `lcr_import_inserts.sql` | INSERT for genuinely new members (rare — typically 0). Seeds `lcr_status='unknown'::member_lcr_status`. |
| `lcr_import_clear_pending.sql` | Marks pending `member_contact_changes` as `synced_to_lcr=true` if the LCR-side value now matches. |
| `lcr_import_moveout_flag.sql` | Sets `activity_status='Check for Moved Out'` on households whose entire member roster is missing from the current LCR pull. Preserves the prior `activity_status` in `prior_activity_status` so it can be restored. **Household-level flagging only** — individual missing members are not auto-flagged. |
| `lcr_import_missing.sql` | Audit list of active members not seen in this LCR pull. Surfaced to the Clerk Report for review. |

Execution order and detailed steps live in the `lcr-import` skill.

## Two-pass name matcher (added 2026-08-27)

The critical invariant. Written to survive LCR name changes without spurious duplicate inserts.

- **Pass 1 (strict):** `COALESCE(m.original_full_name, m.full_name) = l.full_name`. Catches stable rows. This is what `updated_count` reports.
- **Pass 2 (rename fallback):** For LCR rows not caught by pass 1, match on `m.preferred_name = l.preferred_name AND m.household_id = h.id`. Handles LCR full-name changes automatically (marriage, middle name added/dropped, legal change). Reported as `renamed_count`. Also refreshes `original_full_name` to the new LCR name so pass 1 catches it next time.
- **Only after both passes miss** does INSERT run. Reported as `inserted_count`. The insert seeds `original_full_name` to the LCR full name AND `lcr_status='unknown'`.

**Uniqueness proven 2026-08-27:** `(preferred_name, household_id)` is unique across all 600 active members. This is what makes pass 2 safe.

**Never** simplify pass 1 to just `full_name` — the `trg_members_sync_full_name` DB trigger overwrites `members.full_name` with `preferred_name`, preserving the long-form LCR name in `original_full_name`. Removing the COALESCE causes ~300 duplicate inserts per run.

## Dates come in as strings from Google Sheets

Cells like `Birth Date` arrive as strings when the source is the Google Sheet (`'17 Mar 2011'`), not as datetime objects. The `iso_date()` helper in `import.py` parses `'%d %b %Y'`, `'%Y-%m-%d'`, and `'%m/%d/%Y'` in addition to `datetime`/`date` objects.

**This helper broke once (2026-08-27) and silently null-ed 573 birth dates.** Post-import sanity check is now mandatory:

```sql
SELECT COUNT(*) FROM members WHERE is_non_member IS DISTINCT FROM TRUE AND birth_date IS NULL;
```

Expected: 0 or near-zero. Any spike means `iso_date()` is broken again.

## Chunk-staging pattern (added 2026-08-27)

The Supabase `execute_sql` connector has a query-size limit that a single-shot 800 KB INSERT of the full LCR payload exceeds. The importer works around this:

1. Create temp table `_lcr_import_staging (row jsonb)`.
2. Split the LCR JSON payload into ~50 KB chunks. Each chunk is a separate SQL file that does `INSERT INTO _lcr_import_staging SELECT jsonb_array_elements($lcr$…$lcr$::jsonb)`.
3. Run chunks in order. Verify count = record count from the sheet.
4. Run the small (~6 KB) `lcr_import_02_members.sql` that does the UPDATE + INSERT reading from staging.
5. Drop the staging table.

Delegate the chunk loop to a subagent with a tight, no-exploration objective (read chunk, immediately call `execute_sql`, log "chunk N: OK", nothing else) — otherwise accumulated chunk contents overrun the subagent's context.

## Household activity_status: what the importer does and doesn't do

- **New household from LCR:** INSERT with `activity_status='Unknown'`. Belt-and-suspenders — the DB default is also `'Unknown'` (was `'Active'` before 2026-08-29).
- **Existing household still in LCR:** `ON CONFLICT DO UPDATE` refreshes `address, city, state, zip, updated_at`. **Never touches `activity_status`.**
- **Existing household no longer in LCR:** `lcr_import_moveout_flag.sql` sets `activity_status='Check for Moved Out'`, preserving the prior value in `prior_activity_status` so a clerk can restore it if it turns out LCR just missed the household in that export.

## Member lcr_status: what the importer does and doesn't do

- **New member from LCR:** INSERT with `lcr_status='unknown'::member_lcr_status`.
- **Existing member:** the importer NEVER writes `lcr_status`. This is a hard invariant — the full-separation model depends on it.
- **Existing member missing from this LCR pull:** the importer does NOTHING to their `lcr_status`. The member surfaces in the Clerk Report's "Check for Moved Out" section under their household group, with a "Missing + Unknown" amber pill if their status is `unknown`. Clerk decides what to do; if they change status, they do it manually.

The design rationale: LCR pulls occasionally miss a household or a member because of LCR export quirks (permissions, calling changes, whatever). Auto-flipping member status on transient absence would create noise. Household-level flag is safer (family gone = usually all gone) and gives the clerk a review queue.

## Terminal statuses

Members with these statuses are excluded from the moveout audit (they're already terminal, we know they're not "just missing"):

- `deceased`
- `moved_out`
- `name_removed`
- `name_removal_requested`
- `on_mission`

## Repo hygiene

- Generated SQL files are gitignored.
- Any change to `import.py` gets committed + pushed to `gh-pages`:
  ```bash
  cd /home/user/workspace/odessa-ward-app
  git add tools/lcr_import/
  git commit -m "<description>"
  git push origin gh-pages
  ```
  Use `api_credentials=["github"]`.

## Related

- **Operational routine** (step-by-step, connector calls, verification queries): the `lcr-import` user skill.
- **Rendering of missing members in the Clerk Report:** `docs/bundle-patches.md` § "Clerk Report missing-members section (2026-08-29 evening)".
- **Status model:** `docs/status-model.md`.

## Last verified

- 2026-08-29 — written during design-doc consolidation. Reflects the two-pass matcher (2026-08-27), the iso_date bug fix (2026-08-27), the chunk-staging pattern (2026-08-27), and the full-separation model + Unknown defaults (2026-08-29).
