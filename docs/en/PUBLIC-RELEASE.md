# Public release readiness — SourceLore

> **Status: RELEASE BLOCKED, pending history/privacy and first-party licensing review.**
> Baseline inspected: private `main`, commit `8661ebc26f94a83166dc1fa13a7ce8015d96158d`. The owner has requested a **public** GitHub repository; this document records the checks required to make the existing repository public safely.

## 1. Distinguish the two distribution decisions

**First-party repository visibility:** Making SourceLore's own implementation and documentation public allows anonymous browsing of every reachable commit. A Public repository is **not automatically open source**: the repository currently has no root `LICENSE` file. The owner must choose an appropriate first-party license or explicitly publish with no reuse license.

**Third-party knowledge output:** SourceLore's `DISTRIBUTE` gate remains blocked (`distribution_allowed=false`, B-1/B-2/B-3 open). That policy controls captured upstream content, derived outputs and knowledge cards; publishing first-party code must not disable it.

These decisions are independent. See [Security](SECURITY.md), [Requirements](REQUIREMENTS.md) and [Third-party notices](../../THIRD_PARTY_NOTICES.md).

## 2. Confirmed public-release risks

| Finding | Current evidence | Release action |
|---|---|---|
| Private local file paths | Existing security documentation acknowledges paths in historic `progress/` records | Scan current files **and all Git history** |
| History exposure | Previous commits remain accessible after changing a repository to Public | Sanitize reachable objects if sensitive content is found |
| Licensing | No first-party `LICENSE` present | Record an owner-approved license decision |
| Third-party provenance | Six upstream references; one has no license | Independently review attribution and no-copy claims |
| Knowledge data | Raw blobs, snapshots, caches and database must not ship with source | Verify current tree **and prior commits** |
| Secrets | Unknown until exhaustive history scan | Scan, revoke any discovered credentials, and prevent reintroduction |

A normal deletion commit does **not** erase old paths from Git history. Updating `.gitignore` alone is insufficient.

## 3. Reproducible local audit

Run in a full clone, not in a shallow checkout:

```sh
git remote -v
git status --short --branch
git rev-list --objects --all
git log --all --oneline --decorate
git ls-files
```

Review all tracked `progress/` logs, `docs/`, scripts and test fixtures. Search every reachable Git blob for machine usernames, absolute paths, credentials, third-party raw material and data exports. A secret scanner helps, but does not replace manual review. Avoid copying detected secret values into reports.

If historical sanitization is needed: back up the repository and refs; prepare a dedicated rewrite plan with a before/after object inventory; obtain explicit owner approval for commit-ID changes and any force update. **Do not rewrite history as part of routine documentation editing.**

## 4. Publication acceptance checklist

- [ ] First-party licensing decision recorded in both READMEs.
- [ ] Third-party references and B-1/B-2/B-3 obligations reviewed.
- [ ] All reachable branches, tags and commits scanned.
- [ ] Historic usernames, local paths and secrets removed from the history that will be made public.
- [ ] No knowledge databases, content captures or private configuration in Git history.
- [ ] Bilingual requirements, architecture, security and installation docs reviewed against actual CLI.
- [ ] SVG/Mermaid diagrams reviewed as **schematics**, not runtime tests.
- [ ] Coverage truthfully reported (`ROOT_ONLY` does not imply full-tree capture).
- [ ] Independent release review signed off.
- [ ] **After** visibility change, verify anonymous access to README, docs and branch history.

## 5. Deferred actions

This documentation update makes **no** visibility change, chooses **no** license, performs **no** history rewrite and does **not** relax SourceLore runtime distribution gates. These remain explicit release decisions rather than hidden side effects.
