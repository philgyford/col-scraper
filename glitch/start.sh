datasette colmem.db \
  -p 3000 \
  -m datasette_metadata.json \
  --cors \
  --config default_cache_ttl:0

