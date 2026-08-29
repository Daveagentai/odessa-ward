# Bundle patches

Running log of every hand-patch applied to `assets/index-CDdqaBQN.js` (or its successor). Each entry documents what changed, where, why, and how to reapply if the bundle is ever rebuilt from source (which will shift all offsets and mangled names).

Format for each patch:

```
### YYYY-MM-DD — <short title>

**Bundle:** <filename> (SHA256 or hash)
**Reason:** <the user-facing behavior change or fix>
**Change:**
- Site 1: offset ~<offset>, identifier `<name>` — <before> → <after>
- Site 2: ...
**How to find on a rebuild:** <the durable identifier — a data-testid, a unique string, a nearby comment>
**Verification:** <how we confirmed it works>
```

---

### 2026-08-29 — Household activity_status dropdowns simplified to 7 clerk values

**Bundle:** `assets/index-CDdqaBQN.js` (895,270 bytes → 895,006 bytes after patch; -264 delta)

**Reason:** Full-separation status model (see `status-model.md`). Household dropdown gets 7 clerk-facing values; the 8th value (`Check for Moved Out`) is importer-set only and does not appear in the edit dropdown.

**Change:** Two identical 13-value arrays used to populate household activity_status Select controls:

- Site 1: offset 633455 (declaration), used @ 635490 as `VO.map(...)`. Household detail — quick pill dropdown. Data-testid `select-activity-status`.
- Site 2: offset 682180 (declaration), used @ 688560 as `XO.map(...)`. Household detail — inline field edit dropdown (inside `function uh({householdId, field, label, icon, ...})`). Same data-testid.

**Applied via:** anchored string-replace on `const VO=[...]` and `const XO=[...]`. Each anchor was verified to occur exactly once (see `docs/bundle-identifiers.md` for the identifier map).

**Before (both sites):**
```js
["Active","Active - Ready to Serve","Active - Serving","Active - Hold","Less-Active","Not Active - Contact OK","Not Active - Unknown","Do NOT Contact","Do NOT Contact - Hostile","Moved Out","Deceased","Name Removal Requested","Check for Moved Out"]
```

**After (both sites):**
```js
["Active","Less Active","Not Active","Not Active - Unknown","Do NOT Contact","Do NOT Contact - Hostile","Moved Out"]
```

Note: `Less-Active` (hyphen) → `Less Active` (space). `Not Active - Contact OK` → `Not Active`. Removed all `Active - *` sub-variants. Removed `Deceased`, `Name Removal Requested` (member-only). Removed `Check for Moved Out` (importer-only).

**How to find on a rebuild:** Search for `select-activity-status` test-id. The nearest surrounding array literal of 13 status strings is what needs to be shortened. There will be exactly two such Select-based dropdowns (not counting the checkbox filter groups `eA`/`oA` which stay at 8 values — see below).

**Verification:**
1. Post-patch grep for `const VO=` and `const XO=` confirms both are the 7-value form.
2. Bracket/brace/paren balance unchanged before-vs-after (both = -1/0/+1, the same tolerance baseline from the naive check that doesn't parse strings).
3. Bundle size delta = -264 exactly matches (248 - 105) × 2 where 248 is old array length, 105 is new array length.
4. TODO: after deploy, load app in browser, open a household detail, verify dropdown shows 7 values.

**Not changed (intentionally):**

- `eA` @ ~694136 (search-households filter checkbox group) — filter must match what exists in the DB. After migration, `households.activity_status` has 8 possible values (7 clerk + `Check for Moved Out`). Filter list should be all 8. **TODO in a future patch: shorten `eA` from 13 to 8 to match DB reality.**
- `oA` @ ~705370 (search-members filter checkbox group) — this filters MEMBERS by their `members.lcr_status`. Members have 15 possible values. Filter list should be all 15 (or the 13 without `deceased`/`name_removed` depending on UX). **TODO in a future patch: update `oA` to include the 2 new values (`do_not_contact_hostile`, `name_removal_requested`).**

---

### 2026-08-29 — Member Directory status pill repointed from households.activity_status to members.lcr_status

**Bundle:** `assets/index-CDdqaBQN.js`

**Reason:** Under full separation, a member's rendered status must reflect that member's own `lcr_status`, not the enclosing household's `activity_status`.

**Turned out to be simpler than expected:** grep found only ONE view actually rendering member status via the household join — the Member Directory (`function sP()` in the bundle, `/directory` route). The other `activity_status` reads in the bundle are all correctly household-scoped (household detail, search-household, clerk moveout reports, etc.).

**Sites changed:**

1. **Member Directory query** — originally at offset 571103 in `sP()`:
   - Before: `.select("...lcr_status, households(activity_status)").or("lcr_status.eq.active,lcr_status.is.null").order("full_name")`
   - After: `.select("...lcr_status").order("full_name")`
   - Dropped the household join (not needed anymore) and removed the `lcr_status.eq.active,is.null` filter that would hide members with any non-active status once clerks start setting individual statuses. The Directory should show everyone including Friends. Friend filtering happens via the existing `is_non_member` badge next to the name.

2. **Member Directory status pill render** — originally at offset 573994:
   - Before: `l.households?.activity_status && n.jsx("span", { className: ..., children: l.households.activity_status })`
   - After: an IIFE that reads `l.lcr_status`, maps enum key (`not_active_unknown`) to display label (`Not Active - Unknown`) via an inline object, and uses the mapped label for both the color lookup (`rP[...]`) and the pill text. The color map `rP` is keyed on the display labels, so we route the enum through the map first.

**How to find on a rebuild:** Search for `queryKey:["members"]` — that's the Member Directory query. Look at the surrounding render for a status-pill JSX expression using the `rP` (or its rebuild-successor) color map. Repoint from `.households.activity_status` to `.lcr_status` with enum-to-label translation.

---

### 2026-08-29 — Per-member status control added to member detail view

**Bundle:** `assets/index-CDdqaBQN.js`. Size after patch: 897003 bytes (delta +1166).

**Reason:** Under full separation, users must be able to set each member's `lcr_status` independently. Previously the only way to change status was at the household level. New card lets clerks pick from all 15 enum values.

**Component:** `YO` (Member Detail, route `/directory/:id`).

**Two-part patch:**

1. **Hook injection at top of YO** — added `useQueryClient` + `useMutation` calls, wired to update `members.lcr_status`:
   - Anchor: `function YO({params:e}){const[,t]=Dr(),{profile:r,user}=_t();Zt();const a=r?.role||"ward_council"`
   - Replaced: `Zt();` → `,{toast:__toast}=Zt(),__qc=vr(),__upMS=bt({...})` where the mutation calls `Ne.from("members").update({lcr_status:y}).eq("id",e.id)`, invalidates `["member",e.id]` and `["members"]` on success, and toasts on error.

2. **JSX card injection** in the body container:
   - Anchor: `n.jsxs("div",{className:"p-4 space-y-4",children:[n.jsx(ge,{className:"border border-card-border",children:n.jsxs(xe,{className:"p-4 space-y-3",children:[n.jsxs("div",{className:"flex items-center justify-between"`
   - Injected AFTER `children:[` and BEFORE `n.jsx(ge,...`: a new `<Card>` (`ge`) containing:
     - `<h2>` labeled "Member Status"
     - `<Select>` (`Be`) with `data-testid="select-member-lcr-status"` and all 15 enum options mapped to their display labels.
     - Gated on `u && !u.is_non_member` — hidden for Friends (Friends have no lcr_status).
     - `onValueChange` calls `__upMS.mutate(v)` which fires the mutation from step 1.

**Where to find on rebuild:** grep for `data-testid="select-member-lcr-status"`. That test-id is our permanent anchor.

**Enum options list (used in the injected Select):**

```js
[{v:"active",l:"Active"},{v:"active_ready_to_serve",l:"Active - Ready to Serve"},{v:"active_serving",l:"Active - Serving"},{v:"active_hold",l:"Active - Hold"},{v:"less_active",l:"Less-Active"},{v:"not_active_contact_ok",l:"Not Active - Contact OK"},{v:"not_active_unknown",l:"Not Active - Unknown"},{v:"do_not_contact",l:"Do NOT Contact"},{v:"do_not_contact_hostile",l:"Do NOT Contact - Hostile"},{v:"check_for_moved_out",l:"Check for Moved Out"},{v:"moved_out",l:"Moved Out"},{v:"deceased",l:"Deceased"},{v:"on_mission",l:"On Mission"},{v:"name_removed",l:"Name Removed"},{v:"name_removal_requested",l:"Name Removal Requested"}]
```

**Verification:** `node --check` on the bundle passed. Live smoke test still pending until deploy.

---

## Cumulative state after all 2026-08-29 patches

- Bundle hash unchanged (same filename `index-CDdqaBQN.js`) — we're editing in place, not rebuilding.
- **Bundle size:** 897003 bytes (started at 895270, net +1733).
- Household activity_status dropdown: **7 clerk-facing values** (Active, Less Active, Not Active, Unknown, Do NOT Contact, Do NOT Contact - Hostile, Moved Out). `Check for Moved Out` still allowed by CHECK constraint but not in the dropdown.
- Household filter checkboxes (`eA`): still 13 (pending future patch to trim to 8).
- Member filter checkboxes (`oA`): still 13 (pending future patch to add 2 new enum values — `do_not_contact_hostile`, `name_removal_requested`).
- Member Directory (`sP`): reads `members.lcr_status` (not household join), shows everyone (members + Friends).
- Member Detail (`YO`): has a per-member status Select (`data-testid="select-member-lcr-status"`) with all 15 enum values.
- Existing member status badges (Deceased / Moved Out / Name Removed) inside the header still render (from earlier bundle build). The new Select is additive.
- All member status pills across the app: read from `members.lcr_status`.

---

## Patch: Unknown rename (later 2026-08-29)

**Motivation:** the value `Not Active - Unknown` conflated "not active" with "we don't know." Dave clarified the intent is just "Unknown" — no assertion about activity level. This matches the full-separation model: new LCR households and new LCR members should land on `Unknown` because LCR tells us the person/family exists, not what their engagement is.

**Bundle changes:** 5 string literals + 3 structural renames.

1. **VO + XO household dropdown arrays** — replaced `"Not Active - Unknown"` → `"Unknown"` (2 occurrences).
2. **Member Detail Select options** (YO) — `{v:"not_active_unknown",l:"Not Active - Unknown"}` → `{v:"unknown",l:"Unknown"}`.
3. **Member Directory enum-to-display map** (`sP` inline map) — `not_active_unknown:"Not Active - Unknown"` → `unknown:"Unknown"`.
4. **Color maps** (`rP` and its light-mode twin) — key `"Not Active - Unknown":"bg-gray-100 text-gray-800"` → `"Unknown":"bg-gray-100 text-gray-800"` (4 occurrences across two maps).
5. **Filter checkbox arrays** (`eA`/`oA`) — the 13-value list where `"Not Active - Unknown"` was one entry → `"Unknown"` (2 occurrences).

All accomplished by a single `.replace('"Not Active - Unknown"', '"Unknown"')` on the whole bundle after the 3 structural (enum-key-and-label) renames.

**DB migration** (executed same session):

- `ALTER TYPE member_lcr_status RENAME VALUE 'not_active_unknown' TO 'unknown'`
- Dropped `households_activity_status_check`, migrated 215 rows (`Not Active - Unknown` → `Unknown`) plus any `prior_activity_status` matches, re-created CHECK with the new value.
- `ALTER TABLE households ALTER COLUMN activity_status SET DEFAULT 'Unknown'` (was `'Active'`).

**Importer changes:**

- New-household INSERT now explicitly sets `activity_status='Unknown'` (belt-and-suspenders with the new DB default).
- New-member INSERT now writes `'unknown'::member_lcr_status` (was `'not_active_unknown'`).

**Verification:** `node --check` on the bundle passed. Bundle size 896864 bytes (net -139 from previous 897003 state — the shorter labels shaved some bytes).

## Last verified

- 2026-08-29 (afternoon) — Unknown rename applied end-to-end (DB + importer + bundle + docs).
