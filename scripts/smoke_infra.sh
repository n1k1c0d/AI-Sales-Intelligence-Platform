#!/usr/bin/env bash
# Read-only checks for an already running DealMind Compose project.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose config --quiet
api="http://$(docker compose port api 8000)"
n8n="http://$(docker compose port n8n 5678)"
http_get() {
  curl --noproxy '*' --fail --silent --show-error --max-time 10 "$1"
}
check_json() {
  docker compose exec -T api python -c "import json, sys; data = json.load(sys.stdin); $1"
}

http_get "$api/api/v1/health" | check_json "assert data == {'status': 'ok', 'service': 'dealmind-api'}"
http_get "$api/api/v1/ready" | check_json "assert data == {'status': 'ready', 'checks': {'application': 'ok'}}"
http_get "$api/openapi.json" | check_json "assert {'/api/v1/health', '/api/v1/ready'} <= data['paths'].keys()"
swagger_html=$(http_get "$api/docs")
[[ $swagger_html == *SwaggerUIBundle* ]]
echo "PASS: health, application readiness, OpenAPI and Swagger"

sql_result=$(docker compose exec -T db sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -XqtA -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT 1;
SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector' AND extversion <> '');
SELECT abs(('[1,0,0]'::vector(3) <-> '[0,1,0]'::vector(3)) - sqrt(2.0)) < 0.000001;
SQL
)
[[ $sql_result == $'1\nt\nt' ]]
echo "PASS: PostgreSQL, pgvector extension and L2 distance"

n8n_html=$(http_get "$n8n/")
[[ $n8n_html == *'<html'* ]]
http_get "$n8n/healthz/readiness" >/dev/null
docker compose exec -T n8n node -e "
  fetch('http://api:8000/api/v1/health').then(async response => {
    const body = await response.json();
    if (response.status !== 200 || body.service !== 'dealmind-api' || body.status !== 'ok') process.exit(1);
  }).catch(() => process.exit(1))
"
echo "PASS: n8n UI, readiness and n8n-to-API service discovery"
