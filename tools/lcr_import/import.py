#!/usr/bin/env python3
"""
LCR Import Tool (v3.0 — diff-only)

Generates idempotent SQL to upsert households + members from a Bishop CRM
Excel export into the Odessa Ward Supabase database.

WORKFLOW (three phases):
    Phase 1 — SNAPSHOT
        Run the snapshot SQL against Supabase, save output to snapshot.json.
        This returns one row per active member with:
            id, match_full_name, preferred_name, household_name, hash
        The hash is an MD5 of concat_ws('|', ...) over LCR-managed columns.

    Phase 2 — DIFF (this script)
        python3 import.py <xlsx> [sheet-name] [snapshot.json]
        Reads the Excel, computes the SAME hash per row, compares.
        Emits ~5 small SQL files (instead of 24 chunk files).

    Phase 3 — APPLY
        Run the emitted SQL files via Supabase execute_sql. Only members
        whose data actually changed go through staging; all others get a
        cheap presence-ping via bulk UPDATE ... WHERE id = ANY(...).

Usage:
    python3 import.py <path-to-xlsx> [sheet-name] [snapshot.json]

    # Defaults:
    #   xlsx         = /home/user/workspace/Bishop_CRM_Report.xlsx
    #   sheet-name   = first sheet (wb.active)
    #   snapshot.json = /home/user/workspace/db_snapshot.json

    # Special first-run mode: pass 'BOOTSTRAP' as the third arg to emit the
    # snapshot SQL query itself (write it to snapshot.sql) so you can run it
    # via Supabase and save the result as snapshot.json.
    python3 import.py <xlsx> <sheet> BOOTSTRAP

Writes SQL files into the same directory as the xlsx:
    lcr_import_snapshot.sql       (only when BOOTSTRAP)
    lcr_import_households.sql     (~5KB, always)
    lcr_import_changed.sql        (~2-30KB, only rows that changed)
    lcr_import_presence.sql       (~25KB, one bulk UPDATE for all matched IDs)
    lcr_import_inserts.sql        (~1-5KB, only for legit new arrivals)
    lcr_import_clear_pending.sql  (unchanged, small)
    lcr_import_moveout_flag.sql   (unchanged, small)
    lcr_import_missing.sql        (unchanged, read-only audit)

Matching strategy (CRITICAL — unchanged from v2.1):
    Two-pass compound key. Names are NEVER modified in-place.
      Pass 1: COALESCE(original_full_name, full_name) = LCR full_name
      Pass 2: preferred_name + household_id (fallback for renames — also
              refreshes original_full_name so pass 1 catches it next time)
"""
import openpyxl, json, sys, hashlib
from datetime import datetime, date
from pathlib import Path

FILE = sys.argv[1] if len(sys.argv) > 1 else '/home/user/workspace/Bishop_CRM_Report.xlsx'
SHEET = sys.argv[2] if len(sys.argv) > 2 else None
ARG3 = sys.argv[3] if len(sys.argv) > 3 else None
SNAPSHOT_PATH = ARG3 if (ARG3 and ARG3 != 'BOOTSTRAP') else '/home/user/workspace/db_snapshot.json'
BOOTSTRAP = (ARG3 == 'BOOTSTRAP')
OUT_DIR = Path(FILE).parent
OUT = str(OUT_DIR / 'lcr_import.sql')

# --- Snapshot SQL (deterministic hash spec) --------------------------------
# ORDERED list of columns to include in the hash. Order + null coalesce +
# cast rules MUST match Python's compute_hash() below. When you add a column
# here, add it in the SAME position in compute_hash().
HASH_COLUMNS = [
    ('preferred_name', 'text'),
    ('individual_email', 'text'),
    ('individual_phone', 'text'),
    ('address', 'text'),
    ('city', 'text'),
    ('state', 'text'),
    ('zip', 'text'),
    ('gender', 'enum'),
    ('birth_date', 'date'),
    ('birthplace', 'text'),
    ('spouse_name', 'text'),
    ('marriage_date', 'date'),
    ('is_single', 'bool'),
    ('marital_status', 'enum'),
    ('callings', 'text'),
    ('callings_with_dates', 'text'),
    ('temple_recommend_type', 'text'),
    ('temple_recommend_status', 'text'),
    ('temple_recommend_expiration', 'date'),
    ('class_assignment', 'text'),
    ('confirmation_date', 'date'),
    ('has_children', 'bool'),
    ('is_born_in_covenant', 'bool'),
    ('is_convert', 'bool'),
    ('is_sealed_to_current_spouse', 'bool'),
    ('is_sealed_to_parents', 'bool'),
    ('is_sealed_to_prior_spouse', 'bool'),
    ('ministering_brothers', 'text'),
    ('ministering_sisters', 'text'),
    ('mission_country', 'text'),
    ('mission_language', 'text'),
    ('priesthood_office', 'text'),
    ('priesthood', 'text'),
    ('move_in_date', 'date'),
    ('ordination_date', 'date'),
    ('sealing_to_spouse', 'date'),
    ('seminary_status', 'text'),
    ('is_attending_seminary', 'bool'),
    ('potential_seminary_student', 'bool'),
    ('endowment_date', 'date'),
    ('endowment_status', 'text'),
    ('baptism_date', 'date'),
    ('is_returned_missionary', 'bool'),
    ('household_name', 'text'),  # from JOIN — special-cased
]

def build_snapshot_sql():
    """Return the SELECT that produces one row per member with (id, hash, keys)."""
    parts = []
    for col, kind in HASH_COLUMNS:
        if col == 'household_name':
            expr = "COALESCE(h.household_name,'')"
        elif kind == 'text':
            expr = f"COALESCE(m.{col},'')"
        elif kind == 'date':
            expr = f"COALESCE(m.{col}::text,'')"
        elif kind == 'bool':
            expr = f"COALESCE(m.{col}::text,'')"
        elif kind == 'enum':
            expr = f"COALESCE(m.{col}::text,'')"
        else:
            raise RuntimeError(f'unknown kind {kind}')
        parts.append(expr)
    hash_expr = "md5(concat_ws('|',\n    " + ",\n    ".join(parts) + "\n  ))"
    return (
        "SELECT\n"
        f"  {hash_expr} AS h,\n"
        "  m.id,\n"
        "  COALESCE(m.original_full_name, m.full_name) AS match_full_name,\n"
        "  m.preferred_name,\n"
        "  h.household_name\n"
        "FROM members m\n"
        "LEFT JOIN households h ON h.id = m.household_id\n"
        "WHERE m.is_non_member IS DISTINCT FROM TRUE\n"
        "ORDER BY m.id;\n"
    )

if BOOTSTRAP:
    snapshot_sql_path = Path(OUT.replace('.sql', '_snapshot.sql'))
    snapshot_sql_path.write_text(build_snapshot_sql())
    print(f"BOOTSTRAP: wrote {snapshot_sql_path}")
    print(f"Run it via Supabase execute_sql and save the JSON result array to:")
    print(f"  {SNAPSHOT_PATH}")
    print(f"Then re-run this script without BOOTSTRAP.")
    sys.exit(0)

# --- Read Excel ------------------------------------------------------------
wb = openpyxl.load_workbook(FILE, read_only=True, data_only=True)
ws = wb[SHEET] if SHEET else wb.active
print(f"Reading: {FILE}")
print(f"Sheet:   {ws.title}")
rows = list(ws.iter_rows(values_only=True))
header = [h.strip() if h else '' for h in rows[0]]
COL = {name: idx for idx, name in enumerate(header)}

def val(row, col_name):
    idx = COL.get(col_name)
    if idx is None: return None
    v = row[idx]
    if v == '' or v is None: return None
    return v

def yn(v):
    if v is None: return None
    s = str(v).strip().lower()
    if s == 'yes': return True
    if s == 'no': return False
    return None

def iso_date(v):
    if v is None: return None
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, str):
        s = v.strip()
        if not s: return None
        # LCR / Google Sheets string format: '17 Mar 2011'
        for fmt in ('%d %b %Y', '%Y-%m-%d', '%m/%d/%Y'):
            try:
                return datetime.strptime(s, fmt).date().strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None

records = []
for row in rows[1:]:
    if not any(row): continue
    full_name = val(row, 'Full Name')
    if not full_name: continue
    records.append({
        'household_name': val(row, 'Head of House and Spouse') or full_name,
        'full_name': full_name,
        'preferred_name': val(row, 'Preferred Name'),
        'individual_email': val(row, 'Individual E-mail'),
        'individual_phone': val(row, 'Individual Phone'),
        'gender': val(row, 'Gender'),
        'birth_date': iso_date(val(row, 'Birth Date (1 Jan 1990)')),
        'birthplace': val(row, 'Birthplace'),
        'address': val(row, 'Address - Street 1'),
        'city': val(row, 'Address - City'),
        'state': val(row, 'Address - State or Province'),
        'zip': str(val(row, 'Address - Postal Code')) if val(row, 'Address - Postal Code') is not None else None,
        'spouse_name': val(row, 'Spouse Name'),
        'marriage_date': iso_date(val(row, 'Marriage Date')),
        'is_single': yn(val(row, 'Is Single')),
        'marital_status': (
            'Married' if yn(val(row, 'Is Married')) else
            'Widowed' if yn(val(row, 'Is Widowed')) else
            'Divorced' if yn(val(row, 'Is Divorced')) else
            'Single' if yn(val(row, 'Is Single')) else
            None
        ),
        'callings': val(row, 'Callings'),
        'callings_with_dates': val(row, 'Callings with Date Sustained'),
        'temple_recommend_type': val(row, 'Temple Recommend Type'),
        'temple_recommend_status': val(row, 'Temple Recommend Status'),
        'temple_recommend_expiration': iso_date(val(row, 'Temple Recommend Expiration Date')),
        'class_assignment': val(row, 'Class Assignment'),
        'confirmation_date': iso_date(val(row, 'Confirmation Date')),
        'has_children': yn(val(row, 'Has Children')),
        'is_born_in_covenant': yn(val(row, 'Is Born in Covenant')),
        'is_convert': yn(val(row, 'Is Convert')),
        'is_sealed_to_current_spouse': yn(val(row, 'Is Sealed to Current Spouse')),
        'is_sealed_to_parents': yn(val(row, 'Is Sealed to Parents')),
        'is_sealed_to_prior_spouse': yn(val(row, 'Is Sealed to a Prior Spouse')),
        'ministering_brothers': val(row, 'Ministering Brothers'),
        'ministering_sisters': val(row, 'Ministering Sisters'),
        'mission_country': val(row, 'Mission Country'),
        'mission_language': val(row, 'Mission Language'),
        'priesthood_office': val(row, 'Priesthood office'),
        'priesthood': val(row, 'Priesthood'),
        'move_in_date': iso_date(val(row, 'Move In Date')),
        'ordination_date': iso_date(val(row, 'Ordination Date')),
        'sealing_to_spouse': iso_date(val(row, 'Sealing to Spouse')),
        'seminary_status': val(row, 'Seminary Status'),
        'is_attending_seminary': yn(val(row, 'Is Attending Seminary')),
        'potential_seminary_student': yn(val(row, 'Potential Seminary Student')),
        'endowment_date': iso_date(val(row, 'Endowment Date')),
        'endowment_status': val(row, 'Endowment Status'),
        'baptism_date': iso_date(val(row, 'Baptism Date')),
        'is_returned_missionary': yn(val(row, 'Is Returned Missionary')),
    })

# --- Deterministic Python hash mirroring Postgres ---------------------------
def _txt(v):
    if v is None or v == '':
        return ''
    return str(v)

def _bool(v):
    """Postgres bool::text yields 'true' / 'false' / '' for NULL."""
    if v is None:
        return ''
    return 'true' if v else 'false'

def _date(v):
    """Already an ISO string from iso_date(); Postgres date::text is also ISO."""
    if v is None or v == '':
        return ''
    return str(v)

def compute_hash(rec):
    """Compute the same MD5 that build_snapshot_sql() produces server-side.
    ORDER MUST MATCH HASH_COLUMNS. Add fields to BOTH lists together."""
    parts = [
        _txt(rec.get('preferred_name')),
        _txt(rec.get('individual_email')),
        _txt(rec.get('individual_phone')),
        _txt(rec.get('address')),
        _txt(rec.get('city')),
        _txt(rec.get('state')),
        _txt(rec.get('zip')),
        _txt(rec.get('gender')),
        _date(rec.get('birth_date')),
        _txt(rec.get('birthplace')),
        _txt(rec.get('spouse_name')),
        _date(rec.get('marriage_date')),
        _bool(rec.get('is_single')),
        _txt(rec.get('marital_status')),
        _txt(rec.get('callings')),
        _txt(rec.get('callings_with_dates')),
        _txt(rec.get('temple_recommend_type')),
        _txt(rec.get('temple_recommend_status')),
        _date(rec.get('temple_recommend_expiration')),
        _txt(rec.get('class_assignment')),
        _date(rec.get('confirmation_date')),
        _bool(rec.get('has_children')),
        _bool(rec.get('is_born_in_covenant')),
        _bool(rec.get('is_convert')),
        _bool(rec.get('is_sealed_to_current_spouse')),
        _bool(rec.get('is_sealed_to_parents')),
        _bool(rec.get('is_sealed_to_prior_spouse')),
        _txt(rec.get('ministering_brothers')),
        _txt(rec.get('ministering_sisters')),
        _txt(rec.get('mission_country')),
        _txt(rec.get('mission_language')),
        _txt(rec.get('priesthood_office')),
        _txt(rec.get('priesthood')),
        _date(rec.get('move_in_date')),
        _date(rec.get('ordination_date')),
        _date(rec.get('sealing_to_spouse')),
        _txt(rec.get('seminary_status')),
        _bool(rec.get('is_attending_seminary')),
        _bool(rec.get('potential_seminary_student')),
        _date(rec.get('endowment_date')),
        _txt(rec.get('endowment_status')),
        _date(rec.get('baptism_date')),
        _bool(rec.get('is_returned_missionary')),
        _txt(rec.get('household_name')),
    ]
    return hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()

# --- Load snapshot ---------------------------------------------------------
if not Path(SNAPSHOT_PATH).exists():
    print(f"ERROR: snapshot file not found at {SNAPSHOT_PATH}")
    print(f"First, run this script with BOOTSTRAP as the third argument to emit")
    print(f"the snapshot query, then run that query via Supabase and save the")
    print(f"JSON result array to {SNAPSHOT_PATH}.")
    sys.exit(2)

snapshot_rows = json.loads(Path(SNAPSHOT_PATH).read_text())
if isinstance(snapshot_rows, dict) and 'snapshot' in snapshot_rows:
    # Legacy nested shape
    snapshot_rows = snapshot_rows['snapshot']
print(f"Snapshot: {len(snapshot_rows)} member rows loaded from {SNAPSHOT_PATH}")

# Build lookup indexes for two-pass matching (same as SQL logic)
by_match_full_name = {r['match_full_name']: r for r in snapshot_rows}
by_pref_household = {(r['preferred_name'], r['household_name']): r for r in snapshot_rows}

# --- Diff ------------------------------------------------------------------
changed_records = []   # need full UPDATE via staging
new_records = []       # need INSERT
matched_ids = []       # everyone matched (for presence-ping)

renamed_ids = set()    # subset of changed_records: pass-2 matches (need original_full_name refresh)

for rec in records:
    rec_hash = compute_hash(rec)
    # Pass 1: full_name equality
    snap = by_match_full_name.get(rec['full_name'])
    if snap is not None:
        matched_ids.append(snap['id'])
        if snap['h'] != rec_hash:
            rec['_id'] = snap['id']
            rec['_hash'] = rec_hash
            rec['_pass'] = 1
            changed_records.append(rec)
        continue
    # Pass 2: (preferred_name, household_name)
    snap = by_pref_household.get((rec['preferred_name'], rec['household_name']))
    if snap is not None:
        matched_ids.append(snap['id'])
        # Always considered changed (name diverged in LCR -> need original_full_name refresh)
        rec['_id'] = snap['id']
        rec['_hash'] = rec_hash
        rec['_pass'] = 2
        renamed_ids.add(snap['id'])
        changed_records.append(rec)
        continue
    # No match -> INSERT
    new_records.append(rec)

# --- Dedupe households (unchanged from v2) --------------------------------
households = {}
for r in records:
    hn = r['household_name']
    if hn not in households:
        households[hn] = {
            'household_name': hn,
            'address': r['address'],
            'city': r['city'],
            'state': r['state'],
            'zip': r['zip'],
        }

hh_json = json.dumps(list(households.values()), ensure_ascii=False)

def esc(s): return s.replace("'", "''")

# --- households.sql -------------------------------------------------------
# Two-phase household upsert:
#   Phase A: RENAME existing households whose current members overlap by >=50%
#            with an LCR household of a different name. This prevents the
#            LCR-rename-orphan bug: when LCR renames "Cook, Tanner & Jordyn"
#            to "Cook, Tanner Curtis & Jordyn", we UPDATE the row instead of
#            inserting a new one, so members don't lose their household.
#   Phase B: INSERT any LCR households that still don't exist (legit new).
#            UPDATE address/city/state/zip on matched-by-name households.
#
# Build the LCR household -> member list mapping so Postgres can compute overlap.
hh_members = {}
for r in records:
    hn = r['household_name']
    if hn not in hh_members:
        hh_members[hn] = []
    # Match key = COALESCE(original_full_name, full_name) which equals LCR full_name
    # for pass-1 members, or the DB's original_full_name for pass-2 members.
    hh_members[hn].append(r['full_name'])
hh_full_json = json.dumps([
    {
        'household_name': hn,
        'address': households[hn]['address'],
        'city': households[hn]['city'],
        'state': households[hn]['state'],
        'zip': households[hn]['zip'],
        'member_full_names': hh_members[hn],
    }
    for hn in households
], ensure_ascii=False)

sql = f"""
-- =====================================================================
-- Phase A: rename existing households whose member set matches an LCR
-- household with a different name (>=50% overlap of LCR household members
-- with an existing DB household). This fixes the rename-orphan bug where
-- LCR renames a household (e.g. adds a middle name) and the old row is
-- left behind with no members.
-- =====================================================================
WITH lcr_hh AS (
  SELECT * FROM jsonb_to_recordset($lcr${esc(hh_full_json)}$lcr$::jsonb) AS x(
    household_name text, address text, city text, state text, zip text,
    member_full_names jsonb
  )
),
lcr_hh_members AS (
  -- Explode LCR household -> (household_name, member_full_name)
  SELECT l.household_name AS lcr_hh_name, jsonb_array_elements_text(l.member_full_names) AS lcr_mem_name
  FROM lcr_hh l
),
db_matches AS (
  -- For each LCR household, find how many of its members already live in
  -- each existing DB household. Use COALESCE(original_full_name, full_name)
  -- because pass-1 matching in the members phase uses that same key.
  SELECT
    lm.lcr_hh_name,
    m.household_id AS db_hh_id,
    COUNT(*) AS overlap_count
  FROM lcr_hh_members lm
  JOIN members m
    ON COALESCE(m.original_full_name, m.full_name) = lm.lcr_mem_name
   AND (m.is_non_member IS DISTINCT FROM TRUE)
  WHERE m.household_id IS NOT NULL
  GROUP BY lm.lcr_hh_name, m.household_id
),
lcr_hh_size AS (
  SELECT lcr_hh_name, COUNT(*) AS lcr_size FROM lcr_hh_members GROUP BY lcr_hh_name
),
candidates AS (
  -- Rank each LCR household's DB matches; keep only the strongest match
  -- that (a) overlaps >=50%, (b) whose current name differs from LCR,
  -- (c) whose LCR name doesn't already exist as a DB household.
  SELECT
    dm.lcr_hh_name, dm.db_hh_id, dm.overlap_count, s.lcr_size,
    h.household_name AS current_db_name,
    ROW_NUMBER() OVER (
      PARTITION BY dm.lcr_hh_name
      ORDER BY dm.overlap_count DESC, h.household_name
    ) AS rn
  FROM db_matches dm
  JOIN lcr_hh_size s ON s.lcr_hh_name = dm.lcr_hh_name
  JOIN households h ON h.id = dm.db_hh_id
  WHERE dm.overlap_count::float / s.lcr_size >= 0.5
    AND h.household_name IS DISTINCT FROM dm.lcr_hh_name
    AND NOT EXISTS (SELECT 1 FROM households h2 WHERE h2.household_name = dm.lcr_hh_name)
),
renames AS (
  UPDATE households h
  SET household_name = c.lcr_hh_name,
      address = l.address,
      city = l.city,
      state = l.state,
      zip = l.zip,
      updated_at = now()
  FROM candidates c
  JOIN lcr_hh l ON l.household_name = c.lcr_hh_name
  WHERE c.rn = 1
    AND h.id = c.db_hh_id
  RETURNING h.id, c.current_db_name AS old_name, h.household_name AS new_name
)
SELECT COUNT(*) AS renamed_count,
       json_agg(json_build_object('old', old_name, 'new', new_name) ORDER BY new_name) AS renames
FROM renames;

-- =====================================================================
-- Phase B: upsert (insert new / refresh address) by name. Now safe from
-- the rename-orphan bug because any LCR-side renames were resolved above.
-- =====================================================================
WITH lcr_households AS (
  SELECT household_name, address, city, state, zip
  FROM jsonb_to_recordset('{esc(hh_json)}'::jsonb)
    AS x(household_name text, address text, city text, state text, zip text)
)
-- New households INSERT with activity_status='Unknown' per full-separation model (2026-08-29):
-- LCR does not tell us a household's status; clerks set it in the app. Existing
-- households are NEVER touched by this ON CONFLICT DO UPDATE for activity_status
-- (only address/city/state/zip refresh).
INSERT INTO households (household_name, address, city, state, zip, activity_status)
SELECT household_name, address, city, state, zip, 'Unknown' FROM lcr_households
ON CONFLICT (household_name) DO UPDATE SET
  address = EXCLUDED.address,
  city = EXCLUDED.city,
  state = EXCLUDED.state,
  zip = EXCLUDED.zip,
  updated_at = now();
"""
Path(OUT.replace('.sql','_households.sql')).write_text(sql)

# --- changed.sql — only rows whose hash diverged --------------------------
# Uses a single-shot dollar-quoted JSON literal (no chunking — this array is
# tiny compared to the full 800KB import).
if changed_records:
    changed_json = json.dumps(changed_records, ensure_ascii=False)
    changed_sql = f"""
-- Update only members whose data actually changed since last import.
-- lcr_last_seen_at is refreshed here (belt & suspenders with presence.sql).
-- lcr_status is NEVER touched by the importer under the full-separation model
-- (2026-08-29): member status is app-owned only, LCR is not a source for it.
WITH lcr_changed AS (
  SELECT * FROM jsonb_to_recordset($lcr${changed_json}$lcr$::jsonb) AS x(
    _id uuid, _pass int, household_name text, full_name text, preferred_name text,
    individual_email text, individual_phone text, gender text,
    birth_date date, birthplace text, address text, city text, state text, zip text,
    spouse_name text, marriage_date date, is_single boolean, marital_status text,
    callings text, callings_with_dates text, temple_recommend_type text,
    temple_recommend_status text, temple_recommend_expiration date,
    class_assignment text, confirmation_date date, has_children boolean,
    is_born_in_covenant boolean, is_convert boolean, is_sealed_to_current_spouse boolean,
    is_sealed_to_parents boolean, is_sealed_to_prior_spouse boolean,
    ministering_brothers text, ministering_sisters text,
    mission_country text, mission_language text, priesthood_office text, priesthood text,
    move_in_date date, ordination_date date, sealing_to_spouse date, seminary_status text,
    is_attending_seminary boolean, potential_seminary_student boolean,
    endowment_date date, endowment_status text, baptism_date date,
    is_returned_missionary boolean
  )
)
UPDATE members m SET
  household_id = h.id,
  preferred_name = l.preferred_name,
  individual_email = l.individual_email,
  individual_phone = l.individual_phone,
  gender = l.gender::gender_type,
  birth_date = l.birth_date,
  birthplace = l.birthplace,
  address = l.address,
  city = l.city,
  state = l.state,
  zip = l.zip,
  spouse_name = l.spouse_name,
  marriage_date = l.marriage_date,
  is_single = l.is_single,
  marital_status = l.marital_status::marital_status_type,
  callings = l.callings,
  callings_with_dates = l.callings_with_dates,
  temple_recommend_type = l.temple_recommend_type,
  temple_recommend_status = l.temple_recommend_status,
  temple_recommend_expiration = l.temple_recommend_expiration,
  class_assignment = l.class_assignment,
  confirmation_date = l.confirmation_date,
  has_children = l.has_children,
  is_born_in_covenant = l.is_born_in_covenant,
  is_convert = l.is_convert,
  is_sealed_to_current_spouse = l.is_sealed_to_current_spouse,
  is_sealed_to_parents = l.is_sealed_to_parents,
  is_sealed_to_prior_spouse = l.is_sealed_to_prior_spouse,
  ministering_brothers = l.ministering_brothers,
  ministering_sisters = l.ministering_sisters,
  mission_country = l.mission_country,
  mission_language = l.mission_language,
  priesthood_office = l.priesthood_office,
  priesthood = l.priesthood,
  move_in_date = l.move_in_date,
  ordination_date = l.ordination_date,
  sealing_to_spouse = l.sealing_to_spouse,
  seminary_status = l.seminary_status,
  is_attending_seminary = l.is_attending_seminary,
  potential_seminary_student = l.potential_seminary_student,
  endowment_date = l.endowment_date,
  endowment_status = l.endowment_status,
  baptism_date = l.baptism_date,
  is_returned_missionary = l.is_returned_missionary,
  -- pass-2 rows: refresh original_full_name so pass-1 catches this next time
  original_full_name = CASE WHEN l._pass = 2 THEN l.full_name ELSE m.original_full_name END,
  lcr_last_seen_at = now(),
  updated_at = now()
FROM lcr_changed l
JOIN households h ON h.household_name = l.household_name
WHERE m.id = l._id
  AND (m.is_non_member IS DISTINCT FROM TRUE);

SELECT
  (SELECT COUNT(*) FROM (SELECT DISTINCT _id FROM jsonb_to_recordset($lcr${changed_json}$lcr$::jsonb) AS x(_id uuid, _pass int) WHERE _pass = 1) t) AS updated_count,
  (SELECT COUNT(*) FROM (SELECT DISTINCT _id FROM jsonb_to_recordset($lcr${changed_json}$lcr$::jsonb) AS x(_id uuid, _pass int) WHERE _pass = 2) t) AS renamed_count;
"""
    Path(OUT.replace('.sql','_changed.sql')).write_text(changed_sql)
else:
    # Emit an empty result-shaped stub so the runner has something to execute
    Path(OUT.replace('.sql','_changed.sql')).write_text(
        "SELECT 0::int AS updated_count, 0::int AS renamed_count;\n"
    )

# --- presence.sql — bulk presence-ping for all matched IDs ----------------
if matched_ids:
    ids_array = ','.join(f"'{i}'::uuid" for i in matched_ids)
    presence_sql = f"""
-- Presence-ping: refresh lcr_last_seen_at for every member matched by LCR,
-- regardless of whether their data changed. This drives the household-level
-- moveout logic downstream. Runs in one bulk UPDATE — no per-row overhead.
-- lcr_status is NEVER touched here under the full-separation model (2026-08-29):
-- member status is app-owned, and the importer only records "we saw this row"
-- via lcr_last_seen_at.
UPDATE members
SET lcr_last_seen_at = now()
WHERE id = ANY(ARRAY[{ids_array}]);

SELECT {len(matched_ids)}::int AS presence_count;
"""
    Path(OUT.replace('.sql','_presence.sql')).write_text(presence_sql)
else:
    Path(OUT.replace('.sql','_presence.sql')).write_text(
        "SELECT 0::int AS presence_count;\n"
    )

# --- inserts.sql — new arrivals only --------------------------------------
if new_records:
    inserts_json = json.dumps(new_records, ensure_ascii=False)
    inserts_sql = f"""
-- Insert legitimately-new members (not matched by pass 1 or pass 2).
-- original_full_name is seeded to the LCR full_name so pass-1 catches them next run.
WITH lcr_new AS (
  SELECT * FROM jsonb_to_recordset($lcr${inserts_json}$lcr$::jsonb) AS x(
    household_name text, full_name text, preferred_name text,
    individual_email text, individual_phone text, gender text,
    birth_date date, birthplace text, address text, city text, state text, zip text,
    spouse_name text, marriage_date date, is_single boolean, marital_status text,
    callings text, callings_with_dates text, temple_recommend_type text,
    temple_recommend_status text, temple_recommend_expiration date,
    class_assignment text, confirmation_date date, has_children boolean,
    is_born_in_covenant boolean, is_convert boolean, is_sealed_to_current_spouse boolean,
    is_sealed_to_parents boolean, is_sealed_to_prior_spouse boolean,
    ministering_brothers text, ministering_sisters text,
    mission_country text, mission_language text, priesthood_office text, priesthood text,
    move_in_date date, ordination_date date, sealing_to_spouse date, seminary_status text,
    is_attending_seminary boolean, potential_seminary_student boolean,
    endowment_date date, endowment_status text, baptism_date date,
    is_returned_missionary boolean
  )
)
INSERT INTO members (
  household_id, full_name, original_full_name, preferred_name, individual_email, individual_phone, gender,
  birth_date, birthplace, address, city, state, zip, spouse_name, marriage_date,
  is_single, marital_status, callings, callings_with_dates, temple_recommend_type,
  temple_recommend_status, temple_recommend_expiration, class_assignment,
  confirmation_date, has_children, is_born_in_covenant, is_convert,
  is_sealed_to_current_spouse, is_sealed_to_parents, is_sealed_to_prior_spouse, ministering_brothers,
  ministering_sisters, mission_country, mission_language, priesthood_office,
  priesthood, move_in_date, ordination_date, sealing_to_spouse, seminary_status,
  is_attending_seminary, potential_seminary_student, endowment_date, endowment_status,
  baptism_date, is_returned_missionary, lcr_status, lcr_last_seen_at, is_non_member
)
SELECT
  h.id, l.full_name, l.full_name, l.preferred_name, l.individual_email, l.individual_phone, l.gender::gender_type,
  l.birth_date, l.birthplace, l.address, l.city, l.state, l.zip, l.spouse_name, l.marriage_date,
  l.is_single, l.marital_status::marital_status_type, l.callings, l.callings_with_dates, l.temple_recommend_type,
  l.temple_recommend_status, l.temple_recommend_expiration, l.class_assignment,
  l.confirmation_date, l.has_children, l.is_born_in_covenant, l.is_convert,
  l.is_sealed_to_current_spouse, l.is_sealed_to_parents, l.is_sealed_to_prior_spouse, l.ministering_brothers,
  l.ministering_sisters, l.mission_country, l.mission_language, l.priesthood_office,
  l.priesthood, l.move_in_date, l.ordination_date, l.sealing_to_spouse, l.seminary_status,
  l.is_attending_seminary, l.potential_seminary_student, l.endowment_date, l.endowment_status,
  -- New members INSERT with 'unknown' per full-separation model (2026-08-29):
  -- LCR does not tell us a member's status; clerks set it in the app.
  l.baptism_date, l.is_returned_missionary, 'unknown'::member_lcr_status, now(), FALSE
FROM lcr_new l
JOIN households h ON h.household_name = l.household_name
RETURNING id;
"""
    Path(OUT.replace('.sql','_inserts.sql')).write_text(inserts_sql)
else:
    Path(OUT.replace('.sql','_inserts.sql')).write_text(
        "SELECT 0::int AS inserted_count WHERE FALSE;\n"
    )

# --- clear_pending / moveout_flag / missing --------------------------------
#
# NOTE (2026-08-29 full-separation refactor): the individual-level moveout
# sweep (member_moveout_flag.sql) has been REMOVED. Under the new model,
# LCR is not a source of member status — clerks set every member's
# lcr_status manually in the app. When a member disappears from LCR while
# their household stays, that fact is surfaced in the missing.sql report
# below (as an audit list) but the importer no longer writes any status.

missing_sql = """
-- Members in DB with no lcr_last_seen_at touched in the last hour = missing from LCR.
-- This is an audit list only — the importer no longer writes any status here.
-- Clerks review this list and adjust individual member statuses in the app.
--
-- Filter excludes members whose current status already explains their absence
-- from LCR (deceased, moved_out, name_removed, on_mission — these members are
-- not expected to appear in a routine LCR pull).
SELECT id, full_name, household_id, lcr_status
FROM members
WHERE (is_non_member IS DISTINCT FROM TRUE)
  AND (lcr_last_seen_at IS NULL OR lcr_last_seen_at < now() - interval '1 hour')
  AND lcr_status NOT IN ('deceased', 'moved_out', 'name_removed', 'on_mission', 'name_removal_requested')
ORDER BY lcr_status, full_name;
"""
Path(OUT.replace('.sql','_missing.sql')).write_text(missing_sql)

clear_sql = """
UPDATE member_contact_changes mcc
SET synced_to_lcr = TRUE, synced_at = now(), synced_by = 'lcr-import'
FROM members m
WHERE mcc.member_id = m.id
  AND mcc.synced_to_lcr = FALSE
  AND (
    (mcc.field_name = 'individual_phone' AND COALESCE(m.individual_phone,'') = COALESCE(mcc.new_value,''))
    OR (mcc.field_name = 'individual_email' AND COALESCE(m.individual_email,'') = COALESCE(mcc.new_value,''))
    OR (mcc.field_name = 'address' AND COALESCE(m.address,'') = COALESCE(mcc.new_value,''))
    OR (mcc.field_name = 'city' AND COALESCE(m.city,'') = COALESCE(mcc.new_value,''))
    OR (mcc.field_name = 'state' AND COALESCE(m.state,'') = COALESCE(mcc.new_value,''))
    OR (mcc.field_name = 'zip' AND COALESCE(m.zip,'') = COALESCE(mcc.new_value,''))
  )
RETURNING mcc.id;
"""
Path(OUT.replace('.sql','_clear_pending.sql')).write_text(clear_sql)

moveout_sql = """
-- Household-level moveout flag. A household is flagged 'Check for Moved Out'
-- when it has at least one non-terminal member on file but zero members were
-- present in this LCR pull. "Non-terminal" = not deceased, moved_out,
-- name_removed, on_mission, or name_removal_requested — those members are
-- not expected to appear in a routine LCR pull, so we exclude them from the
-- presence math.
WITH hh_status AS (
  SELECT
    household_id,
    COUNT(*) FILTER (WHERE is_non_member IS DISTINCT FROM TRUE
                       AND lcr_status NOT IN ('deceased','moved_out','name_removed','on_mission','name_removal_requested')) AS total_active,
    COUNT(*) FILTER (WHERE is_non_member IS DISTINCT FROM TRUE
                       AND lcr_status NOT IN ('deceased','moved_out','name_removed','on_mission','name_removal_requested')
                       AND lcr_last_seen_at >= now() - interval '1 hour') AS present_now
  FROM members
  WHERE household_id IS NOT NULL
  GROUP BY household_id
),
flagged AS (
  UPDATE households h
  SET prior_activity_status = COALESCE(h.prior_activity_status, h.activity_status),
      activity_status = 'Check for Moved Out',
      updated_at = now()
  FROM hh_status hs
  WHERE h.id = hs.household_id
    AND hs.total_active > 0
    AND hs.present_now = 0
    AND COALESCE(h.activity_status, '') <> 'Check for Moved Out'
  RETURNING h.id, h.household_name
),
restored AS (
  UPDATE households h
  SET activity_status = COALESCE(h.prior_activity_status, 'Active'),
      prior_activity_status = NULL,
      updated_at = now()
  FROM hh_status hs
  WHERE h.id = hs.household_id
    AND hs.present_now > 0
    AND h.activity_status = 'Check for Moved Out'
  RETURNING h.id, h.household_name
)
SELECT
  (SELECT COUNT(*) FROM flagged)  AS flagged_count,
  (SELECT COUNT(*) FROM restored) AS restored_count,
  (SELECT json_agg(household_name ORDER BY household_name) FROM flagged)  AS flagged_households,
  (SELECT json_agg(household_name ORDER BY household_name) FROM restored) AS restored_households;
"""
Path(OUT.replace('.sql','_moveout_flag.sql')).write_text(moveout_sql)

# --- Summary ---------------------------------------------------------------
print(f"Records:   {len(records)}")
print(f"Matched:   {len(matched_ids)}   (Pass 1: {len(matched_ids) - len(renamed_ids)}, Pass 2: {len(renamed_ids)})")
print(f"Changed:   {len(changed_records)}   ({len(changed_records) - len(renamed_ids)} field changes + {len(renamed_ids)} renames)")
print(f"New:       {len(new_records)}")
print()
print("Next: run the SQL files via Supabase in this order:")
print(f"  1. lcr_import_households.sql          (2 phases: renames + upsert)")
print(f"  2. lcr_import_changed.sql             ← {len(changed_records)} rows changed")
print(f"  3. lcr_import_presence.sql            ← {len(matched_ids)} bulk presence pings")
print(f"  4. lcr_import_inserts.sql             ← {len(new_records)} new members (INSERT with 'unknown')")
print(f"  5. lcr_import_clear_pending.sql")
print(f"  6. lcr_import_moveout_flag.sql        (household-level moveout flag ONLY)")
print(f"  7. lcr_import_missing.sql             (audit list of members not in this LCR pull)")
