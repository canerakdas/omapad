# 16. Apps launched from the pad died with the daemon · ✅ Done · S

Steam's own log lines were landing in `journalctl --user -u omapad`, which is
how this surfaced. A child of a systemd service stays in that service's cgroup,
and the default `KillMode=control-group` means `systemctl --user restart
omapad` — which every config change asks for — SIGTERMs the browser or the
game just launched from the menu.

`exec:` now runs through `systemd-run --user --scope --collect`, so the command
gets a unit of its own and outlives the daemon that started it. Gated on
`INVOCATION_ID`: run straight from a checkout there is no cgroup to escape and
nothing to pay for, and if `systemd-run` is missing it warns and spawns plainly
rather than failing to launch. `KillMode=process` was the other option and is
worse — the apps would stay in omapad's cgroup and its journal.
**Verified:** a `Started [systemd-run] …` scope in the journal for a command
the daemon spawned.
