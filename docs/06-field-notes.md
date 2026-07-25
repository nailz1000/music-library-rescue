# 6 — Field notes: the traps that produce confidently wrong answers

Short entries, each earned. The common thread: every one of these made a tool
or a person *sure* of something false.

## Filesystem and shares

- **SMB can show one file twice.** A share backed by a case-sensitive
  filesystem presents entries differing only by case that resolve to the same
  physical file. A dedupe pass that "deletes the duplicate" destroys the only
  copy. Prove two paths are distinct with `os.path.samefile` / `(st_dev,
  st_ino)` before believing a directory listing. (The source library had 86
  such alias groups.)
- **Empty album shells**: leftover folders from old Windows Media Player rips
  (`AlbumArt*.jpg`, `desktop.ini`, no audio) sit beside the real album under a
  differently-cased or year-less name. Name-matching can pick the shell and
  "discover" a missing album. Always pick the candidate with the most audio.
- **Orphan shells can hold the only copy of something.** A truncated-name,
  zero-audio folder held a digital booklet PDF that existed nowhere else, plus
  the cover art the real album folder lacked. Before retiring a shell, rescue
  non-audio valuables (booklets, `cover.jpg`, cue/log/nfo) into the real
  folder — and make the retire tool **refuse any folder containing audio**;
  that one guard is the difference between cleanup and data loss.
- **Windows long paths**: enumeration silently drops paths over 260 chars
  unless you use the `\\?\` prefix. "Silently" means your complete-looking
  plan is missing files and nothing told you.
- **Mojibake is reversible if you don't touch the bytes**: CP1251 text read as
  CP1252 produces recognizable garbage that `s.encode("cp1252").decode("cp1251")`
  restores exactly. Fix the *names*; never "clean up" the files first.

## Process discipline

- **Move deletions to a recycle/quarantine folder, never unlink.** Every
  disposition rule ("uncatalogued → trash") is a judgment call; reversibility
  is what makes bulk judgment calls survivable.
- **A recursive delete guarded by a non-recursive emptiness check** destroyed
  56 files: `os.listdir()` saw no *files* and missed the subfolders holding a
  box set. If the guard and the action don't walk the same tree, the guard is
  decoration. Regression-test guards against a synthetic fixture that would
  have triggered the original loss.
- **Predict, then act, then compare.** Before any merge/consolidation, state
  the expected resulting count (the parts must sum to the whole); after, assert
  it. Five predicted merges landing on five predicted numbers is verification;
  "looks right afterwards" is not.
- **Dry-run against a virtual placement model.** A dry run that checks
  `dest.exists()` can't see two planned moves colliding on a destination that
  doesn't exist yet; simulate the placements.
- **Multiple writers may share the library** (another person, another session,
  a nightly worker, Lidarr itself). Re-read current state before bulk writes;
  collision-check against any in-flight plan.

## Watching long-running work

- **`ps w` lists only processes with a controlling terminal.** It reports every
  `nohup`/`setsid` job as dead — and acting on that false "it died" launched a
  second writer against the same output file (1,265 duplicate records).
  Use `ps -ef`/`pgrep`, and validate any liveness probe against a process you
  know is alive. Better: have the tool take an O_EXCL pidfile lock so a lying
  probe *can't* double-launch it.
- **Query logs by severity, not recency.** "The last 40 log lines are clean"
  meant nothing on a busy logger — the same log had 200 error-level records of
  exactly the failure being checked for. A recency window on a chatty logger is
  100% info noise.
- **A stuck-looking progress bar may be real work that gets thrown away at
  commit** — and a fast-completing "success" may be a queue dedupe returning an
  existing job's id. Verify by outcome (counts moved, rows written), not by
  status strings.
- **Timestamps: know the timezone before computing a skew.** A "7-hour clock
  skew" panic was a UTC timestamp subtracted from local time. (And check the
  host's TZ env spelling — `tz=` with a space silently runs a container on
  UTC.)

## Reporting

- **State what was verified vs assumed.** A "complete" claim based on sampled
  album-level checks missed 29 real per-track upgrades. If a heuristic sampled,
  say it sampled.
- **"No evidence of a problem" ≠ "verified correct."** Keep the two phrases
  distinct in reports; the reader can't tell which checks are load-bearing
  otherwise.
- **When you revise a diagnosis, re-derive it from fresh primary evidence** —
  not from your own last write-up. A wrong "correction" shipped between two
  correct readings because each round anchored on the previous round's prose.
  A correction deserves *more* evidence than the original claim, not less.
- **Alerts that always fire train you to skim.** A triage that flagged three
  permanently-"broken" (actually fine) artists every run taught its reader to
  glance past the summary. Encode known-benign transformations as expectations
  so the report only speaks when reality deviates.
