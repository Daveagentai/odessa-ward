# LCR Import Tool

Pulls a Bishop CRM Excel export from LCR into the Odessa Ward Supabase database, idempotently. Run it as often as you like — re-running the same file is a no-op.

## Standard workflow

1. Download the Bishop CRM report as `.xlsx` (one tab per pull date)
2. Save it as `/home/user/workspace/Bishop_CRM_Report.xlsx` (default path)
3. Tell the agent which sheet to import, e.g. *"Run the LCR import for the May 3, 2026 tab"*
4. Agent runs `python3 import.py <xlsx> "<sheet name>"`, then executes the generated SQL against Supabase project `tmoxwjrivsapriooddqe`
5. Agent reports `updated_count` and `inserted_count`. **Inserted rows = members new since the last pull** — verify each is a real new arrival before accepting.

## What it does

| Step | Effect |
|---|---|
| `lcr_import_households.sql` | Upsert households by `household_name` (address/city/state/zip refreshed) |
| `lcr_import_members.sql` | Upsert members; matches on `COALESCE(original_full_name, full_name) = LCR full_name`. Returns `(updated_count, inserted_count)` |
| `lcr_import_clear_pending.sql` | Auto-clears `member_contact_changes` badges where the new value now matches LCR (i.e. you typed it back in) |
| `lcr_import_missing.sql` | Audit query: who is `lcr_status='active'` in our DB but wasn't in this LCR pull (move-outs, name removals, deceased) |

## Critical: name matching

Members are matched on:
```sql
COALESCE(m.original_full_name, m.full_name) = l.full_name
```

**Why:** the `trg_members_sync_full_name` trigger overwrites `members.full_name` with `preferred_name` on every insert/update, while preserving the long-form LCR name in `original_full_name`. Matching on `full_name` directly causes ~300 duplicate inserts per run. Do not "simplify" this match logic without preserving the COALESCE.

## Edge case: LCR full-name changes

If LCR renames a member (marriage, legal change), the next import will create a duplicate row because both `original_full_name` and the LCR full name no longer match. After import, manually merge the duplicate and update `original_full_name` on the kept row to the new LCR name. This is rare (~1/quarter).

## Files

- `import.py` — generates SQL from the xlsx
- `README.md` — this file

The SQL files are written next to the source `.xlsx` (typically `/home/user/workspace/`) and are not checked into the repo.

## Last verified

May 3, 2026 — 569 active members, 1 friend, 329 households. Test run on May 3 sheet produced 565 updates + 4 legitimate new inserts (Carmichael name change + Oceguera Perez family of 3).
