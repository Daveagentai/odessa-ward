#!/usr/bin/env python3
"""
LCR Import Tool (v2.1)

Generates idempotent SQL to upsert households + members from a Bishop CRM
Excel export into the Odessa Ward Supabase database.

Usage:
    python3 import.py <path-to-xlsx> [sheet-name]

    # Defaults:
    #   xlsx       = /home/user/workspace/Bishop_CRM_Report.xlsx
    #   sheet-name = first sheet (wb.active)

    python3 import.py ../../../Bishop_CRM_Report.xlsx "May 3, 2026"

Writes SQL files into the same directory as the xlsx:
    <xlsx-dir>/lcr_import_households.sql
    <xlsx-dir>/lcr_import_members.sql
    <xlsx-dir>/lcr_import_missing.sql      (read-only audit query)
    <xlsx-dir>/lcr_import_clear_pending.sql
    <xlsx-dir>/lcr_import_moveout_flag.sql (auto-flag households with all members missing)

Matching strategy (CRITICAL):
    Members are matched on COALESCE(m.original_full_name, m.full_name) = l.full_name.
    The trg_members_sync_full_name trigger overwrites members.full_name with
    preferred_name on insert/update, while preserving the long-form LCR name in
    original_full_name. Matching on full_name causes massive duplicate inserts.
"""
import openpyxl, json, sys
from datetime import datetime, date
from pathlib import Path

FILE = sys.argv[1] if len(sys.argv) > 1 else '/home/user/workspace/Bishop_CRM_Report.xlsx'
SHEET = sys.argv[2] if len(sys.argv) > 2 else None
OUT_DIR = Path(FILE).parent
OUT = str(OUT_DIR / 'lcr_import.sql')

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
    return None  # skip anything weird

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

# Dedupe households
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
mem_json = json.dumps(records, ensure_ascii=False)

# Escape single quotes for SQL literal
def esc(s): return s.replace("'", "''")

# Chunk the members JSON list into ~50KB pieces so each staging INSERT fits
# comfortably in one execute_sql call. Uses dollar-quoted strings so the JSON
# doesn't need single-quote escaping.
CHUNK_TARGET_BYTES = 50_000
def chunk_records(recs, target_bytes=CHUNK_TARGET_BYTES):
    out = []
    cur = []
    cur_len = 2  # []
    for r in recs:
        s = json.dumps(r, ensure_ascii=False)
        if cur and cur_len + len(s) + 1 > target_bytes:
            out.append(cur)
            cur = []
            cur_len = 2
        cur.append(r)
        cur_len += len(s) + 1
    if cur: out.append(cur)
    return out

mem_chunks = chunk_records(records)

sql = f"""
-- Upsert households from JSON staging
WITH lcr_households AS (
  SELECT * FROM jsonb_to_recordset('{esc(hh_json)}'::jsonb)
    AS x(household_name text, address text, city text, state text, zip text)
)
INSERT INTO households (household_name, address, city, state, zip)
SELECT household_name, address, city, state, zip FROM lcr_households
ON CONFLICT (household_name) DO UPDATE SET
  address = EXCLUDED.address,
  city = EXCLUDED.city,
  state = EXCLUDED.state,
  zip = EXCLUDED.zip,
  updated_at = now();
"""

Path(OUT.replace('.sql','_households.sql')).write_text(sql)

# Emit staging setup + one chunk file per ~50KB batch + main SQL that reads
# from the staging table. This keeps every execute_sql call under the argv/token
# limits that block passing the full 800KB SQL inline.
setup_sql = """
DROP TABLE IF EXISTS _lcr_import_staging;
CREATE TABLE _lcr_import_staging (data jsonb);
"""
Path(OUT.replace('.sql','_00_setup.sql')).write_text(setup_sql)

for i, chunk in enumerate(mem_chunks):
    chunk_json = json.dumps(chunk, ensure_ascii=False)
    # Dollar-quoted literal — no single-quote escaping needed.
    chunk_sql = f"INSERT INTO _lcr_import_staging(data) SELECT jsonb_array_elements($lcr${chunk_json}$lcr$::jsonb);\n"
    Path(OUT.replace('.sql', f'_01_chunk_{i:02d}.sql')).write_text(chunk_sql)

# IMPORTANT: Match on original_full_name (the long-form LCR name) not full_name.
# The trg_members_sync_full_name trigger overwrites members.full_name to equal
# preferred_name, while the original LCR-style name is preserved in original_full_name.
# Matching on full_name caused 301 duplicate inserts on 2026-05-03. COALESCE handles
# legacy rows where original_full_name was never populated.
members_sql = f"""
WITH lcr_members AS (
  SELECT * FROM jsonb_to_recordset( (SELECT jsonb_agg(data) FROM _lcr_import_staging) ) AS x(
    household_name text, full_name text, preferred_name text,
    individual_email text, individual_phone text, gender text,
    birth_date date, birthplace text, address text, city text, state text, zip text,
    spouse_name text, marriage_date date, is_single boolean, marital_status text,
    callings text, callings_with_dates text, temple_recommend_type text,
    temple_recommend_status text, temple_recommend_expiration date,
    class_assignment text, confirmation_date date, has_children boolean,
    is_born_in_covenant boolean, is_convert boolean, is_sealed_to_current_spouse boolean,
    is_sealed_to_parents boolean, is_sealed_to_prior_spouse boolean, ministering_brothers text, ministering_sisters text,
    mission_country text, mission_language text, priesthood_office text, priesthood text,
    move_in_date date, ordination_date date, sealing_to_spouse date, seminary_status text,
    is_attending_seminary boolean, potential_seminary_student boolean,
    endowment_date date, endowment_status text, baptism_date date,
    is_returned_missionary boolean
  )
),
-- Pass 1: strict match on original_full_name (or full_name if never renamed)
updated_pass1 AS (
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
    lcr_status = 'active',
    lcr_last_seen_at = now(),
    updated_at = now()
  FROM lcr_members l
  JOIN households h ON h.household_name = l.household_name
  WHERE COALESCE(m.original_full_name, m.full_name) = l.full_name
    AND (m.is_non_member IS DISTINCT FROM TRUE)
  RETURNING m.id, l.full_name AS lcr_full_name, l.preferred_name AS lcr_preferred_name, l.household_name AS lcr_household_name
),
-- Pass 2: LCR name changed (marriage / middle name added or dropped). Fall back to
-- (preferred_name, household_name) which is stable across renames and unique across
-- active members. Also refresh original_full_name so pass 1 catches it next time.
updated_pass2 AS (
  UPDATE members m SET
    original_full_name = l.full_name,
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
    lcr_status = 'active',
    lcr_last_seen_at = now(),
    updated_at = now()
  FROM lcr_members l
  JOIN households h ON h.household_name = l.household_name
  WHERE m.preferred_name = l.preferred_name
    AND h.id = m.household_id
    AND (m.is_non_member IS DISTINCT FROM TRUE)
    AND NOT EXISTS (
      SELECT 1 FROM updated_pass1 u WHERE u.id = m.id
    )
    AND NOT EXISTS (
      SELECT 1 FROM updated_pass1 u WHERE u.lcr_full_name = l.full_name
        AND u.lcr_preferred_name = l.preferred_name
        AND u.lcr_household_name = l.household_name
    )
  RETURNING m.id
),
inserted AS (
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
    l.baptism_date, l.is_returned_missionary, 'active', now(), FALSE
  FROM lcr_members l
  JOIN households h ON h.household_name = l.household_name
  WHERE NOT EXISTS (
    SELECT 1 FROM members m
     WHERE COALESCE(m.original_full_name, m.full_name) = l.full_name
       AND (m.is_non_member IS DISTINCT FROM TRUE)
  )
  AND NOT EXISTS (
    SELECT 1 FROM members m
     WHERE m.preferred_name = l.preferred_name
       AND m.household_id = h.id
       AND (m.is_non_member IS DISTINCT FROM TRUE)
  )
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM updated_pass1) AS updated_count,
  (SELECT COUNT(*) FROM updated_pass2) AS renamed_count,
  (SELECT COUNT(*) FROM inserted) AS inserted_count;
"""
Path(OUT.replace('.sql','_02_members.sql')).write_text(members_sql)

# Teardown for the staging table
teardown_sql = "DROP TABLE IF EXISTS _lcr_import_staging;\n"
Path(OUT.replace('.sql','_03_teardown.sql')).write_text(teardown_sql)

# Missing members detection
missing_sql = """
-- Members in DB with no lcr_last_seen_at touched in the last hour = missing from LCR
SELECT id, full_name, household_id, lcr_status
FROM members
WHERE (is_non_member IS DISTINCT FROM TRUE)
  AND (lcr_last_seen_at IS NULL OR lcr_last_seen_at < now() - interval '1 hour')
  AND lcr_status = 'active'
ORDER BY full_name;
"""
Path(OUT.replace('.sql','_missing.sql')).write_text(missing_sql)

# Auto-clear pending badges
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

# Auto-flag households for Check for Moved Out / auto-restore when members reappear.
# Logic:
#   - Only members with lcr_status='active' are counted. Deceased / already-moved-out
#     members are excluded so their households don't get re-flagged on every import.
#   - A household is flagged 'Check for Moved Out' when it has 1+ previously-active
#     members and ZERO of them were refreshed by this LCR pull (i.e. every active
#     member is missing).
#   - When previously-flagged households have any active member refreshed, restore
#     the original activity_status (saved in prior_activity_status) and clear the flag.
#   - Friends (is_non_member=TRUE) are ignored for this calculation.
#   - prior_activity_status is preserved across re-flags (we only set it when flagging
#     a household that is NOT already flagged).
moveout_sql = """
WITH hh_status AS (
  SELECT
    household_id,
    COUNT(*) FILTER (WHERE is_non_member IS DISTINCT FROM TRUE
                       AND lcr_status = 'active') AS total_active,
    COUNT(*) FILTER (WHERE is_non_member IS DISTINCT FROM TRUE
                       AND lcr_status = 'active'
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

print(f"Records: {len(records)}, Households: {len(households)}")
print(f"Chunks: {len(mem_chunks)} (target {CHUNK_TARGET_BYTES} bytes each)")
print(f"Household SQL size: {len(sql)}")
print(f"Members SQL size: {len(members_sql)}")
print(f"\nNext: run the SQL files via Supabase, in this order:")
print(f"  1. {OUT.replace('.sql','_households.sql')}")
print(f"  2. {OUT.replace('.sql','_00_setup.sql')}       (create _lcr_import_staging)")
print(f"  3. {OUT.replace('.sql','_01_chunk_XX.sql')} × {len(mem_chunks)} (populate staging)")
print(f"  4. {OUT.replace('.sql','_02_members.sql')}     ← returns updated_count, inserted_count")
print(f"  5. {OUT.replace('.sql','_03_teardown.sql')}    (drop _lcr_import_staging)")
print(f"  6. {OUT.replace('.sql','_clear_pending.sql')}  (auto-clear synced contact-change badges)")
print(f"  7. {OUT.replace('.sql','_moveout_flag.sql')} (auto-flag/restore Check for Moved Out households)")
print(f"  8. {OUT.replace('.sql','_missing.sql')}        (audit: who's not in this LCR pull)")
