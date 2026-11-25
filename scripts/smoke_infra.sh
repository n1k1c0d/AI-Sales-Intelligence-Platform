#!/usr/bin/env bash
# Read-only checks for an already running DealMind Compose project.
set -euo pipefail
cd "$(dirname "$0")/.."

compose=(docker compose "$@")
"${compose[@]}" config --quiet
api="http://$("${compose[@]}" port api 8000)"
n8n="http://$("${compose[@]}" port n8n 5678)"
web="http://$("${compose[@]}" port web 3000)"
http_get() {
  local response status
  response=$(curl --noproxy '*' --silent --show-error --max-time 10 --write-out $'\n%{http_code}' "$1") || return 1
  status=${response##*$'\n'}
  if [[ $status != 200 ]]; then
    echo "Expected HTTP 200 at $1, got $status" >&2
    return 1
  fi
  printf '%s' "${response%$'\n'*}"
}
check_json() {
  "${compose[@]}" exec -T api python -c "import json, sys; data = json.load(sys.stdin); $1"
}

http_get "$api/api/v1/health" | check_json "assert data == {'status': 'ok', 'service': 'dealmind-api'}"
http_get "$api/api/v1/ready" | check_json "assert data == {'status': 'ready', 'checks': {'application': 'ok', 'database': 'ok'}}"
http_get "$api/openapi.json" | check_json "assert {'/api/v1/health', '/api/v1/ready'} <= data['paths'].keys()"
swagger_html=$(http_get "$api/docs")
[[ $swagger_html == *SwaggerUIBundle* ]]
echo "PASS: health, application readiness, OpenAPI and Swagger"

sql_result=$("${compose[@]}" exec -T db sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -XqtA -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT 1;
SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector' AND extversion <> '');
SELECT abs(('[1,0,0]'::vector(3) <-> '[0,1,0]'::vector(3)) - sqrt(2.0)) < 0.000001;
SQL
)
[[ $sql_result == $'1\nt\nt' ]]
echo "PASS: PostgreSQL, pgvector extension and L2 distance"

http_get "$web/api/health" | check_json "assert data == {'status': 'ok', 'service': 'dealmind-web'}"
http_get "$web/api/system/status" | check_json "from uuid import UUID; assert data['overallStatus'] == data['database']['status'] == 'operational'; assert all(data[k]['status'] == 'operational' and data[k]['httpStatus'] == 200 and UUID(data[k]['requestId']).version == 4 for k in ('backend','readiness')); assert data['backend']['requestId'] != data['readiness']['requestId']"
web_html=$(http_get "$web/")
[[ $web_html == *'System Overview'* ]]
echo "PASS: frontend health, operational BFF probes and System Overview"

n8n_html=$(http_get "$n8n/")
[[ $n8n_html == *'<html'* ]]
http_get "$n8n/healthz/readiness" | check_json "assert data['status'] == 'ok'"
"${compose[@]}" exec -T n8n node -e "
  fetch('http://api:8000/api/v1/health').then(async response => {
    const body = await response.json();
    if (response.status !== 200 || body.service !== 'dealmind-api' || body.status !== 'ok') process.exit(1);
  }).catch(() => process.exit(1))
"
echo "PASS: n8n UI, readiness and n8n-to-API service discovery"
