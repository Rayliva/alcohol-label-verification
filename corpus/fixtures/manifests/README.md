# Malformed manifests (tier 7)

Each must be caught in the pre-flight summary and named with its filename or row number, before any processing starts.

- `missing-image.csv` — A manifest row naming an image that was not uploaded.
- `orphan-image.csv` — An uploaded image with no matching manifest row.
- `bad-row.csv` — A row with fewer columns than the header declares.
- `wrong-columns.csv` — A manifest with the wrong column names entirely.
