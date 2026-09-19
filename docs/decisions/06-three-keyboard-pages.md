# 06. Three pages instead of two · ✅ Done · S

The default grid already ships three pages — `main`, `sym`, `fn` — and the
layer machinery, `L`/`R` cycling and the page keys all handle any number of
pages. Verified against the shipped `LAYOUTS` table: grid cycles
`main → sym → fn`, and the README documents all three. No code change was
needed; the "two pages" assumption in the original write-up was already ahead
of the code.
