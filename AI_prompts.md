# AI Prompt Log — hw5

A log of the prompts I typed into Claude while working on this assignment, in my
own words, organised by problem.

**Convention:** one section per problem. Each section records the problem number
and title, at least one prompt I typed, and — where the first prompt did not get
me what I needed — the follow-up prompt, with a one-line note on what was
lacking. A short note on what Claude did follows each prompt. Sections are filled
in as the assignment progresses; nothing is rewritten after the fact.

---

## Problem 1 — Project setup

**Prompt** — 2026-10-14

> start a hw5 folder

**What Claude did.** Created the `hw5` scaffold matching the hw3/hw4 conventions
(`.gitignore`, `.env.example`, `AI_prompts.md`, `output/`, `prompts/`, `data/`,
`requirements.txt`, `README.md`) and initialised a git repo with a first commit.
No assignment brief existed anywhere under `AI Foundation/`, so it asked for the
hw5 problems rather than guessing at application code.

**Follow-up prompt** _(the first prompt only said where to work, not what to do —
the data still had to be unpacked)_ _(with `~/Desktop/data-2.zip` attached)_

> unzip so you have data/campus_customs.db

**What Claude did.** Extracted the archive into an isolated scratch directory
first (the zip's root is `data-2/`, not `data/`, and it carried `__MACOSX/`
resource-fork noise, which was excluded), checked that it held only `.jpg` and
`.db` files, then moved `campus_customs.db` and `products/` into `hw5/data/`.
The database has four tables — `catalogue` (102 products), `inventory` (612
size rows), `users` (3), `chat_messages` (22) — and every `image_file_path` in
the catalogue resolves to a file in `data/products/` (102 images). Added
`data/` to `.gitignore` so the pack stays local, matching hw4.
