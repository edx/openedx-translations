#!/usr/bin/env bash
set -euo pipefail

# Shared translation runner for translate-po-source-strings workflow.
# Modes:
# - all: process all languages from TRANSLATION_LANGUAGES_JSON
# - single: process one language from SINGLE_TRANSLATION_LANGUAGE_JSON

if [ -z "${APP_NAME:-}" ]; then
  echo "::error::APP_NAME is required."
  exit 1
fi

if [ -z "${LANGUAGE_MODE:-}" ]; then
  echo "::error::LANGUAGE_MODE is required (all|single)."
  exit 1
fi

if [ "$LANGUAGE_MODE" != "all" ] && [ "$LANGUAGE_MODE" != "single" ]; then
  echo "::error::LANGUAGE_MODE must be 'all' or 'single'."
  exit 1
fi

if [ -z "${TRANSLATION_ENDPOINT:-}" ]; then
  echo "::error::TRANSLATION_ENDPOINT is required."
  exit 1
fi

. .github/scripts/fetch_jwt.sh

num_failures=0
num_attempted=0
app_dir="translations/${APP_NAME}"

# Skip the application entirely if its translations directory hasn't been
# populated yet (e.g. a newly added app with no extracted strings).
if [ ! -d "$app_dir" ]; then
  echo "Application directory does not exist: $app_dir. Skipping application."
  exit 0
fi

locale_base=$(find "$app_dir" -type d -path "*/conf/locale" | head -1)

if [ -z "$locale_base" ]; then
  echo "No conf/locale directory found under $app_dir. Skipping."
  exit 0
fi

echo "Found locale base: $locale_base"

en_dir="${locale_base}/en/LC_MESSAGES"

if [ ! -d "$en_dir" ]; then
  echo "::warning::No English source directory found at $en_dir. Skipping."
  exit 0
fi

# Validate chunk size once per job; fall back to 500 if unset or invalid.
if [[ "${TRANSLATION_CHUNK_SIZE:-}" =~ ^[1-9][0-9]*$ ]]; then
  chunk_size="$TRANSLATION_CHUNK_SIZE"
else
  echo "::warning::TRANSLATION_CHUNK_SIZE ('${TRANSLATION_CHUNK_SIZE:-}') is not a positive integer. Falling back to 500."
  chunk_size=500
fi

process_language() {
  local lang_json="$1"

  # Re-fetch JWT per language to prevent token expiry on long-running jobs.
  fetch_jwt || exit 1

  local edxLang repoLang
  edxLang=$(echo "$lang_json" | jq -r '.edxLang')
  repoLang=$(echo "$lang_json" | jq -r '.repoLang')

  echo "Processing language $edxLang for application ${APP_NAME}."

  for source_file in "$en_dir"/*.po; do
    [ -f "$source_file" ] || continue
    po_filename=$(basename "$source_file")

    echo "Processing $po_filename for language $edxLang."

    chunk_dir="/tmp/po_translate_chunks_${APP_NAME}_${po_filename}_${edxLang}"
    chunk_list_file="/tmp/po_translate_chunk_list_${APP_NAME}_${po_filename}_${edxLang}.txt"
    rm -rf "$chunk_dir"

    split_exit_code=0
    python scripts/split_po_file.py \
      --input "$source_file" \
      --output-dir "$chunk_dir" \
      --chunk-size "$chunk_size" > "$chunk_list_file" || split_exit_code=$?

    if [ "$split_exit_code" -ne 0 ]; then
      echo "::warning::Failed to split $po_filename into chunks (exit code $split_exit_code). Skipping."
      num_failures=$((num_failures+1))
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir"
      continue
    fi

    mapfile -t chunk_files < "$chunk_list_file"

    if [ "${#chunk_files[@]}" -eq 0 ]; then
      echo "::warning::Source file has no entries: $source_file. Skipping."
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir"
      continue
    fi

    num_chunks="${#chunk_files[@]}"
    echo "Split into $num_chunks chunk(s)."

    output_file="${locale_base}/${repoLang}/LC_MESSAGES/${po_filename}"
    response_dir="/tmp/po_translate_responses_${APP_NAME}_${po_filename}_${edxLang}"
    rm -rf "$response_dir"
    mkdir -p "$response_dir"

    file_failed=0
    chunk_504=0
    response_files=()

    for chunk_idx in "${!chunk_files[@]}"; do
      chunk_file="${chunk_files[$chunk_idx]}"
      chunk_response="$response_dir/chunk_$(printf '%04d' "$chunk_idx").po"
      response_files+=("$chunk_response")

      echo "Translating chunk $((chunk_idx + 1)) of $num_chunks for language $edxLang."

      # The fetch translations endpoint occasionally times out with a 504 Gateway Timeout error.
      # --retry-all-errors ensures curl retries on 504 responses (not just network errors).
      # Requests that still fail after all retries are soft-failed with a warning.
      curl_exit_code=0
      status_code=$(curl -sS --connect-timeout 10 --max-time 180 --retry 3 --retry-delay 60 --retry-all-errors \
        -w "%{http_code}" \
        -o "$chunk_response" \
        -X POST "$TRANSLATION_ENDPOINT" \
        -F "source_file=@$chunk_file;filename=$po_filename" \
        -F "application_name=${APP_NAME}" \
        -F "translation_language=$edxLang" \
        -H "Authorization: JWT ${JWT_TOKEN}") || curl_exit_code=$?

      if [ "$curl_exit_code" -ne 0 ]; then
        echo "::warning::Curl request failed for chunk $((chunk_idx + 1)) of $num_chunks, language $edxLang, $po_filename, ${APP_NAME} with exit code $curl_exit_code."
        [ -s "$chunk_response" ] && cat "$chunk_response"
        file_failed=1
        break
      fi

      if [ "$status_code" -eq 504 ]; then
        echo "::warning::API call timed out (504) for chunk $((chunk_idx + 1)) of $num_chunks, language $edxLang, $po_filename, ${APP_NAME} after retries. Skipping - will retry on next run."
        [ -s "$chunk_response" ] && cat "$chunk_response"
        chunk_504=1
        break
      fi

      if [ "$status_code" -ne 200 ]; then
        echo "::warning::API call failed for chunk $((chunk_idx + 1)) of $num_chunks, language $edxLang, $po_filename, ${APP_NAME} with status code $status_code."
        [ -s "$chunk_response" ] && cat "$chunk_response"
        file_failed=1
        break
      fi

      echo "Chunk $((chunk_idx + 1)) of $num_chunks succeeded for language $edxLang."
    done

    if [ "$chunk_504" -eq 1 ]; then
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir" "$response_dir"
      continue
    fi

    if [ "$file_failed" -eq 1 ]; then
      num_failures=$((num_failures+1))
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir" "$response_dir"
      continue
    fi

    # Validate that all response chunks are valid PO files before merging.
    all_valid=1
    for response_file in "${response_files[@]}"; do
      if ! CHUNK_FILE="$response_file" python3 -c "import polib,os; polib.pofile(os.environ['CHUNK_FILE'])" 2>/dev/null; then
        echo "::warning::A response chunk for language $edxLang for $po_filename in ${APP_NAME} is not a valid PO file. Skipping."
        all_valid=0
        break
      fi
    done
    if [ "$all_valid" -eq 0 ]; then
      num_failures=$((num_failures+1))
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir" "$response_dir"
      continue
    fi

    mkdir -p "$(dirname "$output_file")"

    if ! python scripts/merge_po_chunks.py \
      --output "${output_file}.tmp" \
      "${response_files[@]}"; then
      echo "::warning::Failed to merge translated chunks for language $edxLang for $po_filename in ${APP_NAME}. Skipping."
      rm -f "${output_file}.tmp"
      num_failures=$((num_failures+1))
      echo ""
      rm -f "$chunk_list_file"
      rm -rf "$chunk_dir" "$response_dir"
      continue
    fi

    mv "${output_file}.tmp" "$output_file"
    git add "$output_file"
    num_attempted=$((num_attempted+1))

    rm -f "$chunk_list_file"
    rm -rf "$chunk_dir" "$response_dir"
    echo ""
  done

  echo ""
}

if [ "$LANGUAGE_MODE" = "all" ]; then
  if [ -z "${TRANSLATION_LANGUAGES_JSON:-}" ]; then
    echo "::error::TRANSLATION_LANGUAGES_JSON is required when LANGUAGE_MODE=all."
    exit 1
  fi
  while IFS= read -r lang; do
    process_language "$lang"

log_git_state() {
  echo "--- git status --short (including untracked) ---"
  git status --short --untracked-files=all || true
  echo "--- git diff --name-status ---"
  git diff --name-status || true
  echo "--- git diff --cached --name-status ---"
  git diff --cached --name-status || true
}
  done < <(echo "$TRANSLATION_LANGUAGES_JSON" | jq -c '.[]')
else
  if [ -z "${SINGLE_TRANSLATION_LANGUAGE_JSON:-}" ]; then
    echo "::error::SINGLE_TRANSLATION_LANGUAGE_JSON is required when LANGUAGE_MODE=single."
  echo "Detected pending changes before commit. Current git state:"
  log_git_state

    exit 1
  fi
  process_language "$SINGLE_TRANSLATION_LANGUAGE_JSON"
fi

# Check if there are any changes to commit. If so, commit and push.
GIT_STATUS=$(git status "translations/${APP_NAME}" -s | wc -l)
if [ "$GIT_STATUS" -gt 0 ]; then
  if [ "$LANGUAGE_MODE" = "single" ] && [ -n "${SINGLE_TRANSLATION_LANGUAGE_JSON:-}" ]; then
    commit_lang=$(echo "$SINGLE_TRANSLATION_LANGUAGE_JSON" | jq -r '.edxLang')
    git commit -m "chore: add AI translated PO strings for ${APP_NAME} (${commit_lang})"
  else
    git commit -m "chore: add AI translated PO strings for ${APP_NAME}"
  fi

  max_push_attempts=3
  push_attempt=1
  push_succeeded=0
  while [ "$push_attempt" -le "$max_push_attempts" ]; do
    if git pull --rebase && git push; then
      push_succeeded=1
      break
    fi

    echo "git pull --rebase && git push failed. Git state at retry $push_attempt/$max_push_attempts:"
    log_git_state

    if [ "$push_attempt" -lt "$max_push_attempts" ]; then
      echo "git push failed due to a concurrent branch update. Retrying ($push_attempt/$max_push_attempts)..."
      sleep $((push_attempt * 5))
    fi
    push_attempt=$((push_attempt+1))
  done
  if [ "$push_succeeded" -ne 1 ]; then
    echo "::error::Failed to push translated strings after $max_push_attempts attempts due to concurrent branch updates."
    exit 1
  fi
fi

if [ "$num_attempted" -eq 0 ]; then
  echo "Warning: No translations were written for application ${APP_NAME}. Check that source PO files exist at the expected path."
fi

if [ "$num_failures" -ne 0 ]; then
  if [ "$LANGUAGE_MODE" = "single" ] && [ -n "${SINGLE_TRANSLATION_LANGUAGE_JSON:-}" ]; then
    err_lang=$(echo "$SINGLE_TRANSLATION_LANGUAGE_JSON" | jq -r '.edxLang')
    echo "One or more translation files for language $err_lang for application ${APP_NAME} failed to be translated. Failing job."
  else
    echo "One or more languages for application ${APP_NAME} failed to be translated. Failing job."
  fi
  exit 1
fi
