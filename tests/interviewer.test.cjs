const { readFileSync } = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const { test } = require("node:test");
const source = readFileSync("src/recovered-app.js", "utf8");
const start = source.indexOf("function interviewerAssignment(");
const end = source.indexOf("function yA(", start);
const ctx = vm.createContext({});
vm.runInContext(source.slice(start, end), ctx);
const plain = x => JSON.parse(JSON.stringify(x));
const id = "2409a4dd-fb10-425d-9d18-4cd0787439d8";
test("Bishopric saves separately from UUID", () => {
  assert.deepEqual(plain(ctx.interviewerAssignment("bishopric")), {
    interview_assigned_to: null, interview_assigned_group: "bishopric"
  });
});
test("person, group, unassigned round-trip and clear previous target", () => {
  let row = ctx.interviewerAssignment(id);
  assert.equal(ctx.interviewerSelection(row), id);
  row = {...row, ...ctx.interviewerAssignment("bishopric")};
  assert.equal(row.interview_assigned_to, null);
  assert.equal(ctx.interviewerSelection(row), "bishopric");
  row = {...row, ...ctx.interviewerAssignment(id)};
  assert.equal(row.interview_assigned_group, null);
  row = {...row, ...ctx.interviewerAssignment("none")};
  assert.equal(ctx.interviewerSelection(row), "");
  assert.equal(row.interview_assigned_to, null);
});
test("existing individual records still display and group works without profile lookup", () => {
  const p = new Map([[id, {full_name: "Test Interviewer", email: ""}]]);
  assert.equal(ctx.interviewerDisplay({interview_assigned_to:id}, p).full_name, "Test Interviewer");
  assert.equal(ctx.interviewerDisplay(ctx.interviewerAssignment("bishopric"), new Map()).full_name, "Bishopric");
  assert.equal(ctx.interviewerDisplay({}, p), null);
});
test("invalid values rejected before DB", () => {
  assert.throws(() => ctx.interviewerAssignment("invalid"), /valid interviewer/);
});
test("both save paths use helper and queue loads group", () => {
  assert.equal((source.match(/\.\.\.interviewerAssignment\(b\)/g) || []).length, 2);
  assert.ok(source.includes("interview_assigned_to, interview_assigned_group, interview_date"));
  assert.ok(source.includes("N(interviewerSelection(ce))"));
  assert.ok(source.includes('["Approved", "Extended", "Accepted", "Sustained"]'));
});
