# Migrations applied AFTER backup snapshot — 2026-06-14

The data + schema dumps in this folder were captured immediately before the
Discussing build started. The following DDL was applied after the snapshot:

## `add_calling_assignments_release_audit` (2026-06-14)

```sql
ALTER TABLE calling_assignments
  ADD COLUMN IF NOT EXISTS released_at timestamptz NULL;

ALTER TABLE calling_assignments
  ADD COLUMN IF NOT EXISTS released_by uuid NULL
    REFERENCES profiles(id) ON DELETE SET NULL;

COMMENT ON COLUMN calling_assignments.released_at IS
  'Precise timestamp when the calling was released (set by the Set Apart auto-prompt or manual Release button).';
COMMENT ON COLUMN calling_assignments.released_by IS
  'Profile id of the bishopric member who recorded the release.';
```

Notes:

- `calling_assignments.member_id` was already nullable in the snapshot — no change needed for the Discussing workflow.
- `calling_assignments.status` is `text NOT NULL` — the new `"Discussing"` value
  requires no DB migration, only app-code support.
- Existing `released_date date` column is retained for backward compatibility
  and clerk-report display; new code writes to `released_at` (timestamptz).
