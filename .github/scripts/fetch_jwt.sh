#!/bin/bash
# Fetches a fresh LMS JWT into $JWT_TOKEN.
# Requires env vars: LMS_ACCESS_TOKEN_URL, EDX_TRANSLATIONS_PROD_CLIENT_ID, EDX_TRANSLATIONS_PROD_CLIENT_SECRET
fetch_jwt() {
  local response_file
  response_file=$(mktemp)
  local curl_exit_code=0
  local status_code
  status_code=$(curl -sS --connect-timeout 10 --max-time 120 \
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

  JWT_TOKEN=$(jq -r '.access_token' "$response_file")
  rm -f "$response_file"

  if [ -z "$JWT_TOKEN" ] || [ "$JWT_TOKEN" = "null" ]; then
    echo "Failed to extract access_token from LMS JWT response."
    return 1
  fi

  # Mask the JWT so as not to inadvertently expose it.
  echo "::add-mask::$JWT_TOKEN"
}
