# Status model

The app tracks activity/engagement status at **two levels**, independently. This doc is the source of truth for what each level means, who owns it, and how they're rendered.

## Invariants (as of 2026-08-29)

- **Household `activity_status` and member `lcr_status` are fully independent.** No cascade, no clamp, no cross-write.
- **LCR is the source of truth for household-level status.** Importer writes `households.activity_status`.
- **LCR is NOT the source of truth for member-level status.** The LCR importer must never write `members.lcr_status` on existing rows.
- **New members from LCR arrive with `lcr_status = 'not_active_unknown'`.** Clerk updates from there.
- **`households.activity_status` has 7 clerk-facing values + 1 importer-set value = 8 total, enforced by a CHECK constraint.**
- **`members.lcr_status` has 15 values in the enum (13 original + 2 added 2026-08-29).**

## Household status (`households.activity_status`)

TEXT column with a `CHECK` constraint (added 2026-08-29). Allowed values:

### 7 clerk-facing values (shown in the dropdown)

| Value | Meaning |
|-------|---------|
| `Active` | Family is engaged with the ward. |
| `Less Active` | Family attends occasionally / on the way in or out. |
| `Not Active` | Family is not attending but contact is welcome. |
| `Not Active - Unknown` | We don't yet know the state of this family. Default for new arrivals. |
| `Do NOT Contact` | Family has asked not to be contacted. |
| `Do NOT Contact - Hostile` | Family has asked not to be contacted, hostile response expected. |
| `Moved Out` | Family has moved out of ward boundaries (LCR-set or clerk-confirmed). |

### 1 importer-set value (not in the clerk dropdown)

| Value | Meaning |
|-------|---------|
| `Check for Moved Out` | LCR importer noticed this household is no longer in the LCR export. Awaits clerk review — clerk either marks `Moved Out` or restores. |

### Mapping applied 2026-08-29 migration

Old values collapsed:

- `Active - Serving` → `Active`
- `Active - Ready to Serve` → `Active`
- `Active - Hold` → `Active`
- `Less-Active` (hyphen) → `Less Active` (space, no hyphen)
- `Not Active - Contact OK` → `Not Active`

Kept as-is: `Active`, `Not Active - Unknown`, `Do NOT Contact`, `Do NOT Contact - Hostile`, `Moved Out`, `Check for Moved Out`.

The pre-migration distribution had 10 distinct values; post-migration has 7 (`Do NOT Contact - Hostile` had zero rows at migration time but is a valid future value).

## Member status (`members.lcr_status`)

PostgreSQL enum `member_lcr_status`. **All 15 values are clerk-facing** (unlike household status, there's no importer-only value).

| Value (enum) | Display | Meaning |
|--------------|---------|---------|
| `active` | Active | Fully engaged. |
| `active_ready_to_serve` | Active - Ready to Serve | Active and ready for a calling. |
| `active_serving` | Active - Serving | Active and currently in a calling. |
| `active_hold` | Active - Hold | Active but temporarily on hold (health, life circumstances). |
| `less_active` | Less-Active | Sporadic engagement. |
| `not_active_contact_ok` | Not Active - Contact OK | Not attending but welcomes contact. |
| `not_active_unknown` | Not Active - Unknown | State unknown. **Default for LCR imports.** |
| `do_not_contact` | Do NOT Contact | Requested no contact. |
| `do_not_contact_hostile` | Do NOT Contact - Hostile | Added 2026-08-29. Requested no contact, hostile response expected. |
| `check_for_moved_out` | Check for Moved Out | Manually flagged for review (importer no longer sets this). |
| `moved_out` | Moved Out | Confirmed moved out (clerk-set). |
| `deceased` | Deceased | Deceased (clerk-set). |
| `on_mission` | On Mission | Serving a full-time mission. |
| `name_removed` | Name Removed | Records removed. |
| `name_removal_requested` | Name Removal Requested | Added 2026-08-29. Records removal pending. |

## Who writes what

| Field | LCR importer | Clerk / app |
|-------|--------------|-------------|
| `households.activity_status` | Yes (LCR is source of truth for household state; importer syncs) | Yes (clerks override, especially `Check for Moved Out` → `Moved Out` or restore) |
| `members.lcr_status` on **existing** rows | **Never** | **Only** |
| `members.lcr_status` on **new-from-LCR** rows | Seeds `not_active_unknown` at INSERT | Then clerks update |

## Rendering rules

- Anywhere a **household's** engagement/activity level is shown, render `households.activity_status`.
- Anywhere a **member's** engagement/activity level is shown, render `members.lcr_status`.
- These are independent facts. Family status card and member cards inside that household may show different states — that's correct, not a bug.

Rendering of member status previously read `households(activity_status)` (via the members table's joined household). That was wrong once we separated the two levels. The 2026-08-29 patch repoints those reads.

## Distribution snapshots

### 2026-08-29 pre-migration (households)

```
Not Active - Unknown      215
Active - Serving           49
Active                     39
Not Active - Contact OK    21
Check for Moved Out         7
Active - Ready to Serve     5
Less-Active                 4
Moved Out                   3
Active - Hold               2
Do NOT Contact              1
```

### 2026-08-29 post-migration (households)

```
Not Active - Unknown  215
Active                 95   (39 + 49 + 5 + 2 = 95 ✓)
Not Active             21
Check for Moved Out     7
Less Active             4
Moved Out               3
Do NOT Contact          1
```

### 2026-08-29 (members, unchanged this migration)

```
active                 596
deceased                 2
check_for_moved_out      1
moved_out                1
```

All 596 `active` values were LCR-defaulted, not clerk-set. Clerks are expected to overwrite as they minister.

## Last verified

- 2026-08-29 — status model rewritten from "Hostile clamp / cascade" design to full-separation design. Migration applied. Docs written.
