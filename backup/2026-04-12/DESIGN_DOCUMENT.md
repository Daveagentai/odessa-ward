# Odessa Ward CRM - Design Document
## Version 1.1 — Snapshot: April 12, 2026

---

## Overview
The Odessa Ward CRM is a custom-built web application for managing ward (church congregation) operations. It serves as a centralized tool for the bishopric and ward council to track members, households, callings, visits, tasks, and ministering assignments.

## Architecture

### Frontend
- **Framework**: Vite + React (bundled as static SPA)
- **Styling**: Tailwind CSS
- **Hosting**: Cloudflare Workers (static site)
- **URL**: https://odessa-ward.dhoussian.workers.dev/
- **Source**: GitHub repo `Daveagentai/odessa-ward` (gh-pages branch)

### Backend
- **Database**: Supabase (PostgreSQL 17.6)
- **Project ID**: tmoxwjrivsapriooddqe
- **Region**: us-west-2
- **Auth**: Supabase Auth with email/password
- **RLS**: Row-Level Security enabled on all tables (except ministering_assignments)

---

## Database Schema

### Tables & Row Counts (as of April 12, 2026)

| Table | Rows | RLS |
|-------|------|-----|
| members | 567 | Yes |
| households | 311 | Yes |
| ministering_assignments | 274 | No |
| calling_assignments | 150 | Yes |
| callings | 83 | Yes |
| tasks | 15 | Yes |
| profiles | 12 | Yes |
| visits | 6 | Yes |
| bishop_notes | 0 | Yes |
| leadership_notes | 0 | Yes |

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

---

## Features (v1.1)

### Member Directory
- 567+ members with full LCR data
- Search, filter by status/organization
- Individual member detail pages
- Skills/talents tracking

### Household Management
- 311 households with addresses and geocoding
- Household map view (Leaflet/OpenStreetMap)
- Activity status tracking (Active, Less-Active, Not Active, etc.)
- Emergency preparedness data

### Callings Directory & Workflow
**Status Flow**: Proposed → Approved → Extended → Accepted → Sustained → Set Apart → Active
**Additional statuses**: On Hold, Pending Release, Released, Declined

**Workflow Features**:
- Propose members for callings with notes
- Approve/decline proposals
- Assign interviewers with "can_interview" flag on profiles
- Mark Extended/Accepted/Sustained/Set Apart
- **Revert to Proposed** button for Approved, Extended, and Accepted statuses
  - Approved → Proposed: clears approved_by, approved_date
  - Extended → Proposed: also clears extended_date
  - Accepted → Proposed: also clears accepted_date
- Release with reason and date tracking
- On Hold with Resume & Propose / Resume & Approve options
- Clerk report with LCR reconciliation, type indicators, and dates
- Timeline and notes on calling detail pages

### Visit Notes
- Record visits by type (Home Visit, Phone Call, etc.)
- Sensitivity levels for privacy control
- Follow-up tracking
- Permission levels (Bishop-only visits restricted)

### Task Management
- Create tasks linked to members/households
- Priority levels and due dates
- Assign to specific users or bishopric
- Organization-based filtering
- Permission level filtering

### Ministering Assignments
- Brothers and sisters assignments
- 274 active assignments
- Linked to members and households

### Access Control
**Roles with permission hierarchy**:
1. Bishop — Full access, admin functions
2. Bishopric — Most access
3. Executive Secretary — Administrative access
4. Ward Clerk — Record-keeping access
5. RS/EQ Presidents — Organization-specific access
6. Ward Council — Basic access

**RLS Policies** enforce access control at the database level.

---

## Deployment
- Frontend builds via Vite → static assets in `assets/` directory
- Deployed to Cloudflare Workers via `wrangler.jsonc` config
- GitHub Pages branch (`gh-pages`) serves as deployment source

## Authentication
- Bishop account: bishopdavehoussian@gmail.com
- Supabase Auth with email/password
- Session tokens via refresh_token flow
