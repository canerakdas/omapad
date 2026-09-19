# 01. Cycle through empty workspaces too · ✅ Done · S

`L`/`R` use `workspace = 'r+1'`, and the *r* means **range** — it walks every
workspace in the monitor's range instead of skipping the empty ones (`e` =
existing). Shipped config and the daemon test now agree on `r+1`.

**Caveat (still open):** `r±1` follows the monitor's workspace range and does
not stop at ten. If you want a fixed 1–10 loop, omapad should hold the number
itself and dispatch the absolute id, which also makes wrap-around predictable.
