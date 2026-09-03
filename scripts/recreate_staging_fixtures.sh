#!/usr/bin/env bash
# Recreates staging-only test fixture accounts that a production->staging DB
# sync wipes out (docs/TESTING_REBUILD_SPEC.md §3.2 deliberately keeps these
# OFF production -- see owl_system/docs/TESTING_SYSTEM.md's Test Accounts
# section -- so "recreate on staging after each sync" is the accepted manual
# cost, same reasoning as scripts/recreate_local_fixtures.sh's local
# equivalent). Run this on staging (otdev1602) after every "push live to
# staging" sync, same trigger as running the local script after a local sync.
#
# Idempotent: safe to run whether or not the account currently exists, and
# whether or not it has the right role/password already.
#
# Connects over SSH using the keypair set up 2 Sept 2026 (public key added to
# the WP Engine User Portal's SSH Keys section) rather than local wp-cli.phar
# + --path, since this script has no local filesystem access to the staging
# install. WP Engine's own `wp` binary is already on the remote $PATH and
# needs no wp-cli.yml override there (unlike locally -- confirmed 2 Sept 2026
# the monorepo's local-only, gitignored wp-cli.yml that forces --user=root
# doesn't exist on the deployed staging filesystem) -- --user=1 is passed
# explicitly anyway for parity with the local script and because ID 1 is
# confirmed to be a real administrator account on staging.
#
# Only covers the client + tutor accounts (the two GitHub Secrets-driven
# fixtures smoke-tests.yml actually authenticates as on staging/CI --
# TEST_CLIENT_EMAIL/PASSWORD, TEST_TUTOR_EMAIL/PASSWORD). Deliberately omits
# the admin (role=owl) account and the blog video_id fixture that
# recreate_local_fixtures.sh also sets: smoke-tests.yml's env block has no
# TEST_ADMIN_EMAIL/PASSWORD, meaning admin_credentials-gated tests
# (admin-metabox/admin-dashboard) never run against staging/CI at all and
# so need no staging-side fixture; same for the video_id fixture, which
# test_video_object_json_ld doesn't require server-side setup for beyond
# what's already in the synced content.
#
# Usage: bash scripts/recreate_staging_fixtures.sh
#   (run from anywhere; paths below are absolute)
#
# Credentials: prefers TEST_CLIENT_*/TEST_TUTOR_*/TEST_MEET_NOW_TUTOR_ID
# already present in the environment (CI's smoke-tests.yml exports these from
# GitHub Secrets before this step runs), falling back to reading them from
# the local .env when they aren't -- the same single source of truth
# recreate_local_fixtures.sh uses, per TESTING_SYSTEM.md's "keep these
# accounts permanently configured on both Local and staging". Either way it's
# one value per account, never two to keep in sync.
#
# SSH key: WPENGINE_SSH_KEY (path to the private key) overrides the default
# local path -- CI writes the key from a GitHub Secret to a runner temp file
# and points this at it, since it obviously can't use a path on this machine.

set -euo pipefail

SSH_HOST="otdev1602@otdev1602.ssh.wpengine.net"
SSH_KEY="${WPENGINE_SSH_KEY:-$HOME/.ssh/owltutors_wpengine_staging}"
ENV_FILE="$(dirname "$0")/../.env"

WP() {
    ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new -i "$SSH_KEY" "$SSH_HOST" wp "$@" --user=1
}

# Only read .env for whichever of these aren't already set in the
# environment -- avoids requiring a .env file in CI, where these arrive as
# real env vars instead, and avoids a second, possibly-stale source of truth
# locally where .env already provides them.
if [ -z "${TEST_CLIENT_EMAIL:-}" ] || [ -z "${TEST_CLIENT_PASSWORD:-}" ] || [ -z "${TEST_TUTOR_EMAIL:-}" ] || [ -z "${TEST_TUTOR_PASSWORD:-}" ] || [ -z "${TEST_MEET_NOW_TUTOR_ID:-}" ]; then
    if [ ! -f "$ENV_FILE" ]; then
        echo "Error: TEST_CLIENT_*/TEST_TUTOR_*/TEST_MEET_NOW_TUTOR_ID not fully set in the" >&2
        echo "environment, and $ENV_FILE not found to fall back to." >&2
        exit 1
    fi
    : "${TEST_CLIENT_EMAIL:=$(grep -E '^TEST_CLIENT_EMAIL=' "$ENV_FILE" | cut -d= -f2-)}"
    : "${TEST_CLIENT_PASSWORD:=$(grep -E '^TEST_CLIENT_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)}"
    : "${TEST_TUTOR_EMAIL:=$(grep -E '^TEST_TUTOR_EMAIL=' "$ENV_FILE" | cut -d= -f2-)}"
    : "${TEST_TUTOR_PASSWORD:=$(grep -E '^TEST_TUTOR_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)}"
    : "${TEST_MEET_NOW_TUTOR_ID:=$(grep -E '^TEST_MEET_NOW_TUTOR_ID=' "$ENV_FILE" | cut -d= -f2-)}"
fi

if [ -z "$TEST_CLIENT_EMAIL" ] || [ -z "$TEST_CLIENT_PASSWORD" ]; then
    echo "Error: TEST_CLIENT_EMAIL / TEST_CLIENT_PASSWORD could not be resolved from the" >&2
    echo "environment or $ENV_FILE." >&2
    exit 1
fi

echo "== Test client: $TEST_CLIENT_EMAIL =="
if WP user get "$TEST_CLIENT_EMAIL" --field=ID >/dev/null 2>&1; then
    echo "  exists -- ensuring role=client and password matches .env"
    WP user set-role "$TEST_CLIENT_EMAIL" client
    WP user update "$TEST_CLIENT_EMAIL" --user_pass="$TEST_CLIENT_PASSWORD" >/dev/null
else
    echo "  missing -- creating fresh"
    WP user create "$TEST_CLIENT_EMAIL" "$TEST_CLIENT_EMAIL" \
        --role=client \
        --user_pass="$TEST_CLIENT_PASSWORD" \
        --display_name="Test Client"
fi
WP user get "$TEST_CLIENT_EMAIL" --fields=ID,user_login,roles

# Test tutor: password only, never auto-created -- same reasoning as
# recreate_local_fixtures.sh: a usable test tutor needs real profile data
# (tuition_delivery, availability outcome, name fields) that a bare
# `wp user create` can't reproduce, so a missing tutor account here needs
# manual ACF profile setup, not an automated fix.
if [ -n "$TEST_TUTOR_EMAIL" ] && [ -n "$TEST_TUTOR_PASSWORD" ]; then
    echo
    echo "== Test tutor: $TEST_TUTOR_EMAIL =="
    # WP-CLI's output on this environment carries a stray leading BOM on every
    # invocation (confirmed 2 Sept 2026: not present in wp-config.php,
    # owl_system.php, owltheme's functions.php, any WP Engine mu-plugin, or
    # shell profile/motd files -- harmless CLI-output noise from somewhere
    # deeper in the stack, not the CLAUDE.md BOM-in-a-PHP-file risk, but it
    # was enough to break a plain string comparison below). Strip it plus any
    # stray whitespace before comparing.
    if actual_id_raw=$(WP user get "$TEST_TUTOR_EMAIL" --field=ID 2>/dev/null); then
        # A WP user ID is always plain digits -- stripping to digits-only
        # sidesteps the BOM entirely rather than trying to match its exact
        # byte sequence, and also covers ordinary trailing whitespace/CR.
        actual_id=$(printf '%s' "$actual_id_raw" | tr -cd '0-9')
        expected_id=$(printf '%s' "$TEST_MEET_NOW_TUTOR_ID" | tr -cd '0-9')
        echo "  exists -- ensuring password matches .env (role/profile data left untouched)"
        WP user update "$TEST_TUTOR_EMAIL" --user_pass="$TEST_TUTOR_PASSWORD" >/dev/null
        WP user get "$TEST_TUTOR_EMAIL" --fields=ID,user_login,roles

        # TEST_MEET_NOW_TUTOR_ID (a separate GitHub Secret / .env value) is
        # this same account's WP user ID, used directly as tutor_id by
        # owl_create_test_job -- unlike the client account, this ID can't be
        # silently "fixed" by this script since GitHub Secrets aren't
        # writable from here; just surface drift so it can be corrected
        # manually rather than causing confusing test failures downstream.
        if [ -n "$expected_id" ] && [ "$actual_id" != "$expected_id" ]; then
            echo "  WARNING: staging's actual ID ($actual_id) does not match" >&2
            echo "  TEST_MEET_NOW_TUTOR_ID in .env/GitHub Secrets ($expected_id)." >&2
            echo "  Update TEST_MEET_NOW_TUTOR_ID to $actual_id or Stage 3/4/Live test-job" >&2
            echo "  creation will silently use the wrong tutor." >&2
        fi
    else
        echo "  MISSING -- cannot auto-create (needs manual ACF profile setup, see TESTING_SYSTEM.md)" >&2
    fi
else
    echo
    echo "(TEST_TUTOR_EMAIL/PASSWORD not set in .env -- skipping tutor fixture check)"
fi

echo
echo "Done. Add more fixture accounts to this script as they're found to need it."
