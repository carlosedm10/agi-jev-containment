---
name: generate-pr-description
description: Generate a GitHub PR description by analyzing git diffs. When the user is working on a feature branch and needs to create a PR description, use this skill to automatically summarize the most important changes and new logic. The skill compares the current (or specified) branch against the default branch and generates a markdown description ready to paste into GitHub. Mention this skill when the user asks to "create a PR description", "generate PR summary", "write a PR", "document changes", or needs to explain what changed in their branch.
---

# Generate PR Description

## What This Does

Analyzes the diff between the branch and the default branch and generates a **short,
plain-language** PR description in this template:

- **🚪 Why?** — the problems this PR exists to solve, in one short paragraph
- **🔑 What?** — a handful of bold-led paragraphs, one per theme
- **🏡 Context** — links to sibling PRs / dependencies, only when they exist

The output is a starting point the author refines. It must read like a teammate explaining the
PR out loud, not like an engineering log.

If the repo has its own PR template (`.github/pull_request_template.md`), use its headings and
apply the style rules below inside them.

## How to Use It

- "Generate my PR description"
- "Create a PR description for this branch"
- Optionally name a branch: "Generate PR description for `feature/auth`"

## Step 1: Get the Diff

```bash
BASE=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
git diff --stat $(git merge-base "$BASE" HEAD)
git diff $(git merge-base "$BASE" HEAD)
```

Include uncommitted working-tree changes if the user is describing work not yet committed. For
huge diffs, read `--stat` first and then the files that matter; don't try to narrate every file.

## Step 2: Find the Themes, Not the Files

Group the diff into 4–8 **themes** — a theme is something a reviewer or a teammate would care
about as one idea ("uploads are virus-scanned before storage", "multi-region creates are
all-or-nothing"), never a file or a class. Everything that doesn't deserve its own theme goes
into a single `Cleanups:` paragraph, or is dropped.

## Step 3: Write It — the style rules

This is the part that matters. The house style is **concise and plain**:

1. **Why? is one short paragraph.** The user-visible problems only — what broke, what was
   risky, what was annoying. No architecture, no history.
2. **Each What? theme is one paragraph: a bold plain-language claim, then 1–3 simple
   sentences.** The bold lead states the outcome ("**Multi-region creates are all-or-nothing.**"),
   the sentences after say just enough to make it concrete.
3. **At most one or two identifiers per paragraph.** Name the entry point (`createInvoice`,
   `handleUpload`) so reviewers can find it; do not enumerate helpers, types, files, or
   constants.
4. **No defensive rationale, no incident history, no design essays.** "Why we didn't do X", "an
   earlier revision did Y", bound/limit enumerations, and invariant proofs belong in code
   comments or review threads — never in the body.
5. **Translate jargon.** "The browser calls the backend directly" beats "the orchestration moved
   behind the API contract boundary". If a sentence needs the reader to know internal codenames
   to parse it, rewrite it.
6. **Bugs fixed along the way get half a sentence each**, inside the theme they belong to
   ("Fixed along the way: the new-plan save didn't persist").
7. **One `Cleanups:` paragraph** for small unrelated improvements, and optionally one
   `Coverage:` line if the tests are worth calling out.
8. **One paragraph = one line.** Never hard-wrap markdown prose.
9. **Total budget: the whole body fits on one screen** (~150–250 words per PR is the norm; a
   giant PR may reach ~350). If the draft runs longer, merge or cut themes — do not compress by
   densifying sentences.

### Example (the calibration target)

```markdown
## 🚪 Why?

Uploading a file was the least trustworthy path in the product. Anything a user attached went straight to storage unchecked, a failed multi-file upload left half the batch behind, and the only signal the author got back was a spinner that eventually stopped — with no way to tell a rejected file from a slow one.

## 🔑 What?

**Uploads are scanned before they are stored.** The API accepts the file into a quarantine bucket, scans it, and only then promotes it; a rejected file never reaches the public bucket.

**Batch uploads are all-or-nothing.** A batch validates every file first, then writes, and cleans up storage if anything fails mid-way — a failed batch can no longer leave orphaned blobs that count against the user's quota.

**The uploader tells you what happened.** Per-file status, the real rejection reason, and a retry that only re-sends the files that failed.

**Quota checks moved to the server.** `createUpload` is now the single place the limit is enforced, so the browser can't be talked out of it. Fixed along the way: the quota counter double-counted replaced files.

Cleanups: the upload component was split into small focused pieces, and the storage client's retry logic moved into a tested class — which immediately caught a real bug.

## 🏡 Context

- [💻 Other PR](https://github.com/acme/mobile/pull/412) — the mobile-side half.
```

### Anti-example (what to avoid)

> **Uploads are scanned.** `createUpload` takes the multipart body and its content hash and
> returns a promoted blob handle; the API owns the whole deterministic half in
> `UseCases::Uploads::PromoteScanned`: it re-derives the content type from the same sniffer the
> client used (never trusting the header), resolves the bucket policy, builds a quarantine key,
> strips path prefixes, rejects a partial body via a truncation guard measured against
> `Content-Length`, refuses a payload past `MAX_UPLOAD_BYTES`…

Same content, wrong altitude: it enumerates the implementation, names five internals, and argues
design rationale. Reviewers read the code for that.

## Step 4: Output

Emit the markdown in a code block, using exactly:

```markdown
## 🚪 Why?

[one short paragraph]

## 🔑 What?

[4–8 bold-led theme paragraphs, then optional Cleanups:/Coverage: paragraphs]

## 🏡 Context

[only if there are sibling PRs, dependencies, or docs worth linking — otherwise omit the section]
```
