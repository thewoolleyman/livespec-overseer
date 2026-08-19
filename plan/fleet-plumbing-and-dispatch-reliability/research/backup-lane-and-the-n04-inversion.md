# The backup lane, and why `overseer-n04`'s remedy inverts

Measured 2026-08-19T19:30–19:50Z. This note exists because the finding it
records changes what a P1 carrier MEANS, and a finding that large should be
reviewable in SCM rather than living only as a ledger comment. Research is
filesystem-held; the coordination record stays on the plan epic.

**Nothing here was mutated.** No grant was issued, no server state changed, no
valve turned. Every statement below is a read.

## What the carrier says

`overseer-n04` (P1) records that `bd` writes in this tenant are not
backup-exported: auto-backup warns `command denied to user livespec-overseer`
on every write while the exit code stays 0. It calls this **a silent
durability hole**. A later measurement found the denial uniform across eight
probed tenants and escalated accordingly — if the grant template is at fault,
the fix is one change applied for **eleven** tenants rather than one.

Its stated open question was the exact GRANT required, left undetermined for
want of server-side access.

## The question is answered, and the answer is that no grant should be added

### 1. The tenant grant is database-scoped by design

`dolt-server`'s `scripts/onboard-tenant.sh` issues exactly:

```sql
GRANT ALL PRIVILEGES ON `<db>`.* TO '<user>'@'%';
```

Its own comment states **"No cross-database grants"**, citing
`SPECIFICATION/constraints.md` §"Authentication and least privilege". So the
uniform denial across every probed tenant is not eight misconfigurations and
not a template omission — **it is the template working as specified.**

### 2. Backup administration is withheld from the ops user too

`scripts/backup-sync.sh` records that the privilege Dolt requires for
`CALL DOLT_BACKUP` is one that `${OPS_USER}` **must not hold** — which is why a
separate `${BACKUP_USER}` identity exists at all. Backup administration is
excluded from every non-backup identity deliberately, tenants included.

### 3. The writes are already backed up — measured, not inferred

A central lane backs up every tenant database on a timer:

- `dolt-backup.service`, described verbatim as *"dolt-server S3 backup sync
  (`CALL DOLT_BACKUP('sync','s3')` for every tenant DB)"*, driven by an active
  `dolt-backup.timer`.
- **Last run 2026-08-19 20:03:09 CEST, exit `0/SUCCESS`** — nineteen minutes
  before this measurement began.
- Coverage is by **enumeration**, not a hard-coded list: `list_tenant_databases`
  runs `SHOW DATABASES` minus the system schemas, so a tenant is included
  automatically.
- **Exit 0 is a strong signal here, not a weak one.** A per-database sync
  failure sets a non-zero rc, and `assert_backup_remote_coverage` independently
  fails the run if any live tenant still lacks the `s3` remote.

### 4. And this tenant specifically is covered — the last leg, closed

An earlier version of this finding had to fence point 3: the backup run's
journal is privileged and unreadable from this account, so tenant inclusion
rested on enumeration + coverage assertion + exit 0. That is a strong chain and
it was still an inference.

It is now a direct read. Querying this tenant's own database:

```
$ mysql --skip-ssl -h 127.0.0.1 -P 3307 -u livespec-overseer -D livespec-overseer \
    -N -e "SELECT name FROM dolt_backups;"
s3
```

**The `s3` backup remote is registered on `livespec-overseer` itself**, which is
precisely the condition the coverage assertion enforces and the target
`DOLT_BACKUP('sync','s3')` writes to.

Note also **what is absent**: `s3` is the only row. `bd`'s attempted
`backup_export` remote does not exist, exactly as its denial implies. So the two
halves agree — the central backup is registered and working; `bd`'s own
registration never happened and never needed to.

## Therefore the premise is refuted and the remedy inverts

What the carrier documents is `bd` attempting to register **its own second
backup remote as the tenant user** — a redundant registration by an identity the
architecture deliberately excludes from backup administration, duplicating a
backup that already runs on a timer with its own coverage assertion. It fails,
warns, and exits 0.

**That is a noise and exit-code-honesty defect, not a durability one.**

### Why this matters more than a resizing

The carrier's escalation points at the grant template, "probably ONE fix", for
eleven tenants. **Implemented as a grant, that hands eleven tenant SQL users a
backup-administration privilege the specification withholds and the ops user is
explicitly forbidden to hold** — dismantling the isolation boundary in order to
duplicate a backup that already happens. The escalation would have multiplied
the wrong fix elevenfold, and the item reads P1 precisely because the durability
framing made it urgent.

**Grant nothing.** The remedy is to stop `bd` attempting the registration in
these tenants, or to make the failure honest in its exit code and suppress the
expected warning.

If the item is closed as "known and accepted", the recorded reason must be **that
backup is covered centrally** — not that a risk is tolerated. Those two close
reasons look alike and only one is true.

## This is the plan's signature defect in its most expensive form

The opening scope note says every carrier here "fails in a way that points away
from its own fix". Here the failure text — `command denied` — points squarely at
a missing grant, which is the one action that must not be taken. Every earlier
instance in this plan cost an investigation. This one would have cost a security
boundary.

## Scope

- **Measured directly**: the grant statement and its stated rationale; the
  ops/backup identity split and its stated reason; the enumeration, per-database
  failure handling and coverage assertion in `backup-sync.sh`; the systemd unit
  description, timer state and last-run exit status; and this tenant's own
  `dolt_backups` contents.
- **Still not established**: which specific privilege the `backup_export`
  *registration* requires. That it is withheld by design rests on the identity
  split and the database-scoped grant rather than on a privilege-table read,
  which tenant credentials deliberately cannot perform. This does not affect the
  conclusion — coverage is now measured directly rather than argued from the
  grant model.
