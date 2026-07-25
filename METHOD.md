# Method — how this was made, and with what

Full transparency about the apparatus behind this repo: the software it drives,
the data sources it queries, and the human+AI workflow that produced it.

## The stack this knowledge applies to

| layer | software | role |
|---|---|---|
| media server | **Plex** (music agent `tv.plex.agents.music`, **Prefer local metadata** ON) | renders the library; its grouping behavior is chapter 1 |
| collection manager | **Lidarr** | download/upgrade automation; chapter 5 |
| metadata authority | **MusicBrainz** (`musicbrainz.org/ws/2`) | release shapes, by release ID |
| tag I/O | **mutagen** (Python) | all tag reads/writes; header-level audio properties |
| audio analysis | **ffmpeg** | Chromaprint fingerprints (built-in muxer — no separate fpcalc), `volumedetect` for fake-hi-res and live-detection measurements |
| storage | a NAS share (SMB, case-sensitive backing filesystem, btrfs, native recycle bin) | the traps in chapters 4–6 |

No paid services, no proprietary APIs, no databases beyond SQLite where the
apps themselves use it.

### Data-source etiquette

- **MusicBrainz**: identify yourself with a real `User-Agent` (app name +
  contact), pace ~1 request/second, expect 503s anyway, retry with backoff,
  and **cache by release ID on disk** so re-runs cost zero. Measured
  sustainable throughput during this project: ~0.4 req/s.
- **Plex/Lidarr APIs**: poll the cheapest signal (a status flag), not the
  payload; a 15-second full-payload poll crashed the server twice
  (playbook L18).

## The working method

Four artifacts, kept in git, doing different jobs:

1. **The guide** (`docs/`) — narrative knowledge: how the systems behave and
   why. Written for a reader who has the problem but not the history.
2. **The playbook** (`PLAYBOOK.md`) — incident-derived lessons, numbered and
   citable. Written *while the mistake stings*, with the real numbers.
3. **The decision register** (`DECISIONS.md`) — intentional choices with
   reasoning, narrow scope, and a "revisit if" trigger, so odd-looking choices
   don't get "fixed" back into bugs.
4. **The tools** (`tools/`) — everything the docs assert, executable. Dry-run
   by default; `--apply` is a separate decision made after reading the plan.

In the source project these were backed by a fifth artifact that doesn't
translate to a public repo: a **ticket queue** (one file per problem, moved
from `open/` to `done/` with the evidence written in). The pattern worth
copying: *any discovered problem gets a ticket, even when fixed inline* — the
ticket is where the numbers and the failed theories live, and it's what the
playbook entries were later distilled from.

Process rules that did the most work:

- **Reversibility before judgment**: every delete is a recycle-bin move, so a
  wrong judgment call costs a restore, not a loss.
- **Prediction before action**: state the expected post-operation count, then
  assert it (playbook L24).
- **Layered diagnosis**: cheapest layer first, stop at the broken one
  (chapter 2).
- **Controls before trust**: every new measurement gets a known-positive and a
  known-negative before its output drives anything (playbook L8).

## The human + AI workflow

This project — the rescue itself and this repo — was executed as a
collaboration between the library's owner and **Claude (Anthropic), running in
Claude Code** sessions:

- **The owner** set goals and disposition rules ("keep the higher quality
  copy", "trash means recoverable", "a distinct release shows its own year"),
  made every judgment call the tools escalated, reviewed dry-run plans before
  `--apply`, ran the privileged steps (anything needing root on the NAS), and
  caught several of the AI's mistakes — including the misread that became
  playbook L28.
- **Claude** wrote the tools and documentation, ran the analyses, and did the
  bulk file/tag/API work — under the constraints above, with its mistakes
  documented in the playbook alongside everyone else's. Notably: the 56-file
  loss (L7), the double-writer incident (L27), and the wrong mid-diagnosis
  (L28) were all AI mistakes, caught by verification discipline or by the
  owner, and are recorded rather than sanded off.
- **Session-persistent knowledge** — the same rules now in this repo — was
  maintained as a "skill" file the AI loads at the start of each working
  session, which is why lessons stopped being re-learned. If you work with an
  AI assistant on your own library, that pattern (a per-project rules file the
  assistant must read before bulk operations) is the single highest-leverage
  piece of this setup.

Commits authored or co-authored by the AI carry a `Co-Authored-By: Claude`
trailer. The measured numbers throughout (thresholds, failure rates, timings)
come from the actual runs, not estimates.

## What this repo deliberately does not contain

- anything identifying the source environment (hosts, paths, credentials,
  account names) — sanitized at extraction, verified by grep;
- the source library's ticket archive (environment-specific);
- tooling coupled to one environment (NAS runbooks, per-host scripts). The
  three tools included are the ones that run anywhere.
