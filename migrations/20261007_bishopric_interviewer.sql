-- Keep individual profile UUIDs separate from the Bishopric group option.
ALTER TABLE public.calling_assignments
  ADD COLUMN interview_assigned_group text;
ALTER TABLE public.calling_assignments
  ADD CONSTRAINT calling_interviewer_group_valid
  CHECK (interview_assigned_group IS NULL OR interview_assigned_group = 'bishopric'),
  ADD CONSTRAINT calling_interviewer_single_target
  CHECK (interview_assigned_group IS NULL OR interview_assigned_to IS NULL);
COMMENT ON COLUMN public.calling_assignments.interview_assigned_group IS
  'Group interviewer assignment. bishopric means bishop or either counselor; individual users remain in interview_assigned_to.';
