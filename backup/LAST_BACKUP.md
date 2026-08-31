# Last Backup

**Date:** 2026-08-29 (initial run) — mirror script upgraded 2026-08-31
**Time zone:** America/New_York

## What was backed up

| Component | Location | Details |
|---|---|---|
| Code repo | `Daveagentai/odessa-ward` gh-pages @ `61d6883` | Full working tree, committed and pushed |
| DB dump | `backup/db-snapshots/2026-08-29.sql` | 1,621 rows across 12 tables, 1.78 MB |
| LCR exports | `backup/lcr-exports/` | 3 files: Aug.23.2026, July.18.2026, June.25.2026 |
| Google Drive mirror | folder `1ktKT-XumyJq808Jkw5EbYg1lfccA6lYh` | 102 files uploaded (101 initial + mirror script itself) |

## DB row counts

| Table | Rows |
|---|---|
| bishop_notes | 0 |
| calling_assignments | 198 |
| callings | 97 |
| households | 346 |
| leadership_notes | 0 |
| member_contact_changes | 6 |
| members | 601 |
| ministering_assignments | 274 |
| profiles | 14 |
| tasks | 20 |
| visit_attendees | 33 |
| visits | 32 |
| **Total** | **1,621** |

## Mirror behavior

The Drive mirror script lives at `tools/drive_mirror/mirror.py`. On each run:

- Files with matching MD5 → skipped (no upload, no revision noise)
- Files that differ → updated on the same Drive file ID (new revision, old bytes preserved in revision history)
- Brand-new files → created
- Files removed from the repo → left alone in Drive (no trash sweep)
- Date-stamped snapshots accumulate — that's history

## Quarterly archive

Scheduled task `46ab3bda` fires on Jan 1, Apr 1, Jul 1, Oct 1 at 9am ET. It notifies Dave asking whether to snapshot the current mirror into a dated archive folder. Live mirror is untouched.

## Next backup

Time-based reminder threshold: 30 days from the last successful run. Otherwise, on explicit request.
