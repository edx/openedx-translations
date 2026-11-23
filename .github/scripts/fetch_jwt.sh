#!/bin/bash
# Provides an LMS JWT in $JWT_TOKEN.
# Requires env vars: LMS_ACCESS_TOKEN_URL, EDX_TRANSLATIONS_PROD_CLIENT_ID, EDX_TRANSLATIONS_PROD_CLIENT_SECRET
#
# Callers run `fetch_jwt` before every language (and every package) so long jobs never use an
# expired token. To avoid sending hundreds of token requests in a few minutes, which the LMS
# rate-limits with 429 and which used to fail the whole job, the token is reused until it is
# close to expiring, and transient failures (429, 5xx, network errors) are retried.
#
# Optional env vars:
#   JWT_REFRESH_MARGIN_SECONDS  fetch a new token this long before expiry (default 300)
#   JWT_DEFAULT_TTL_SECONDS     lifetime to assume if the response has no expires_in (default 900)
#   JWT_FETCH_RETRY_DELAY       seconds between retries of the token request (default 30)
fetch_jwt() {
  local now
  now=$(date +%s)
  local margin="${JWT_REFRESH_MARGIN_SECONDS:-300}"

  # Reuse the current token while it has more than $margin seconds left.
  if [ -n "${JWT_TOKEN:-}" ] && [ -n "${JWT_EXPIRES_AT:-}" ] && [ "$now" -lt $((JWT_EXPIRES_AT - margin)) ]; then
    return 0
  fi

  local response_file
  response_file=$(mktemp)
  local curl_exit_code=0
  local status_code
  status_code=$(curl -sS --connect-timeout 10 --max-time 120 \
    --retry 3 --retry-delay "${JWT_FETCH_RETRY_DELAY:-30}" --retry-all-errors \
    -w "%{http_code}" \
    -o "$response_file" \
    -X POST "$LMS_ACCESS_TOKEN_URL" \
    -d "grant_type=client_credentials" \
    --data-urlencode "client_id=$EDX_TRANSLATIONS_PROD_CLIENT_ID" \
    --data-urlencode "client_secret=$EDX_TRANSLATIONS_PROD_CLIENT_SECRET" \
    -d "token_type=jwt") || curl_exit_code=$?

  if [ "$curl_exit_code" -ne 0 ]; then
    echo "Curl request to fetch LMS JWT failed with exit code $curl_exit_code."
    rm -f "$response_file"
    return 1
  fi

  if [ "$status_code" -ne 200 ]; then
    echo "API call to fetch LMS JWT failed with status code $status_code."
    rm -f "$response_file"
    return 1
  fi

  local token
  token=$(jq -r '.access_token' "$response_file")
  local expires_in
  expires_in=$(jq -r '.expires_in // empty' "$response_file")
  rm -f "$response_file"

  if [ -z "$token" ] || [ "$token" = "null" ]; then
    echo "Failed to extract access_token from LMS JWT response."
    return 1
  fi

  if ! [[ "$expires_in" =~ ^[0-9]+$ ]]; then
    expires_in="${JWT_DEFAULT_TTL_SECONDS:-900}"
  fi

  JWT_TOKEN="$token"
  JWT_EXPIRES_AT=$((now + expires_in))

  # Mask the JWT so as not to inadvertently expose it.
  echo "::add-mask::$JWT_TOKEN"
}
