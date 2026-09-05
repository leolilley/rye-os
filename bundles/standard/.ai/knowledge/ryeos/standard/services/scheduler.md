<!-- ryeos:signed:2026-08-11T02:28:40Z:0a5517278357f12227abfc49d64b9e72fad820f541b40bc0923414fbd1cfb14a:k3rZqnDDi0DQubEnvqoupeYr9dZS38hsp1GObRyKQI04u8ld7ACnT+FATJVPGr2bB5hpw0TUdVAwT3Sq9N50Cw==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
---
category: ryeos/standard/services
tags: [service, scheduler, workflows]
version: "1.0.0"
description: Scheduler service reference.
---

# Services: scheduler

Invariant: scheduler services manage recurring workflow execution specs and fire history in daemon state.

Services: `scheduler/register`, `scheduler/list`, `scheduler/deregister`, `scheduler/pause`, `scheduler/resume`, and `scheduler/show_fires`.

`scheduler/register` requires an explicit complete schedule contract:
`schedule_id`, `item_ref`, `schedule_type`, `expression`, object `params`,
`timezone`, `misfire_policy`, `overlap_policy`, positive
`lateness_grace_secs`, boolean `enabled`, a sorted unique non-empty
`capabilities` subset, and a complete `execution_policy`. `project_root` must
be absent for projectless execution and present for both explicit
`live_direct` and `pinned` project execution. No scheduling or execution-policy
field is defaulted by the daemon.

Registration seals the authenticated principal's current grant generation
into the schedule authority. Every fire revalidates that exact grant and the
declared capability subset before launching. A `live_direct` fire intentionally
resolves the live project again at each fire and recovery and is never
implicitly snapshotted. A `pinned` fire binds one durable
`current_head` or explicit `snapshot` authority and retains it through recovery;
it never falls back to the live tree. Scheduled execution does not permit
interactive `capture_live`.

The admitted fire context is exposed without changing ordinary item
parameters: graph and directive expressions use `execution.schedule`, while a
direct subprocess tool reads the identical canonical JSON projection from the
protected `RYEOS_EXECUTION_CONTEXT` environment variable. Recovery preserves
that exact context; a later fire receives a different `fire_id`. External
observation actions should bind that ID explicitly so recovery replays the same
fire while a later fire receives a fresh observation coordinate.

Scheduler descriptors live in standard because scheduled work is a workflow-layer feature that launches directives/graphs through the normal execution runner.
