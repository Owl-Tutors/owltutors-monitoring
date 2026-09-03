#!/usr/bin/env bash
# Recreates local-only test fixture accounts that a production->local DB sync
# wipes out (docs/TESTING_REBUILD_SPEC.md §3.2 deliberately keeps these
# OFF production -- see owl_system/docs/TESTING_SYSTEM.md's Rebuild Status
# section -- so "recreate locally after each sync" is the accepted manual
# cost instead of a permanent fixture on live data).
#
# Idempotent: safe to run whether or not the account currently exists, and
# whether or not it has the right role/password already. Run this once after
# every "pull live to local" sync.
#
# Usage: bash scripts/recreate_local_fixtures.sh
#   (run from anywhere; paths below are absolute)

set -euo pipefail

WP_PATH="C:/laragon/www/owltutors"
PHP_BIN="/c/laragon/bin/php/php-8.3.30-Win32-vs16-x64/php.exe"
WP_CLI="$WP_PATH/wp-cli.phar"
ENV_FILE="$(dirname "$0")/../.env"

# wp-cli.yml at the monorepo root defaults every command to --user=root,
# which doesn't exist locally and breaks every command identically --
# override it explicitly on every call below.
WP() {
    "$PHP_BIN" "$WP_CLI" "$@" --path="$WP_PATH" --user=1
}

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found -- copy .env.example or create it first." >&2
    exit 1
fi

# Source only the values needed, without executing the rest of the file.
TEST_CLIENT_EMAIL=$(grep -E '^TEST_CLIENT_EMAIL=' "$ENV_FILE" | cut -d= -f2-)
TEST_CLIENT_PASSWORD=$(grep -E '^TEST_CLIENT_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
TEST_TUTOR_EMAIL=$(grep -E '^TEST_TUTOR_EMAIL=' "$ENV_FILE" | cut -d= -f2-)
TEST_TUTOR_PASSWORD=$(grep -E '^TEST_TUTOR_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
TEST_ADMIN_EMAIL=$(grep -E '^TEST_ADMIN_EMAIL=' "$ENV_FILE" | cut -d= -f2-)
TEST_ADMIN_PASSWORD=$(grep -E '^TEST_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)

if [ -z "$TEST_CLIENT_EMAIL" ] || [ -z "$TEST_CLIENT_PASSWORD" ]; then
    echo "Error: TEST_CLIENT_EMAIL / TEST_CLIENT_PASSWORD not set in $ENV_FILE" >&2
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

# Test tutor: password only, never auto-created. Unlike the client, a usable
# test tutor needs real profile data set up (tuition_delivery, availability
# outcome, name fields -- see TESTING_SYSTEM.md's Test Accounts section), so
# a bare `user create` here would produce an account that exists but doesn't
# actually work for Stage 3/4 or tutor-dashboard tests. Found live 26 Aug
# 2026: this account already existed with the correct role but a stale
# password, which cascaded into 13 failing/erroring tests across
# test_tutor_dashboard.py and test_job_connection.py (the latter via the
# stage3_job fixture, which logs the tutor in as part of its own setup).
if [ -n "$TEST_TUTOR_EMAIL" ] && [ -n "$TEST_TUTOR_PASSWORD" ]; then
    echo
    echo "== Test tutor: $TEST_TUTOR_EMAIL =="
    if WP user get "$TEST_TUTOR_EMAIL" --field=ID >/dev/null 2>&1; then
        echo "  exists -- ensuring password matches .env (role/profile data left untouched)"
        WP user update "$TEST_TUTOR_EMAIL" --user_pass="$TEST_TUTOR_PASSWORD" >/dev/null
        WP user get "$TEST_TUTOR_EMAIL" --fields=ID,user_login,roles
    else
        echo "  MISSING -- cannot auto-create (needs manual ACF profile setup, see TESTING_SYSTEM.md)" >&2
    fi
else
    echo
    echo "(TEST_TUTOR_EMAIL/PASSWORD not set in .env -- skipping tutor fixture check)"
fi

# test_video_object_json_ld (test_content.py) needs at least one blog post
# with the 'video_id' ACF field set, within the first page of the blog
# listing (page-blog.php shows 12/page). Production→local syncs wipe this
# like any other postmeta if the source post never had it set for real
# (found 26 Aug 2026: no post in the synced DB had video_id set at all,
# despite the field being live on the site). Reuses a real Owl Tutors
# YouTube ID already in use elsewhere (a tutor's featured_video) rather than
# a placeholder. Post 194262 ("The Proven Benefits of One-to-One Tuition")
# is real editorial content, not a test fixture -- if it's gone or has moved
# far enough down the listing after a future sync, pick a current recent
# post instead and update the ID below.
# Real staff (role=owl) session for admin_credentials (tests/conftest.py) --
# needed by the admin-metabox and admin-dashboard tests, which are the only
# ones in this suite that need genuine wp-admin access rather than the
# custom front-end /login/ form. LOCAL-ONLY -- never synced to/from
# production or staging, same reasoning as the client/tutor fixtures above
# (docs/TESTING_REBUILD_SPEC.md §3.2). Auto-created (unlike the tutor
# fixture) since an 'owl' account needs no extra ACF profile data to be
# usable, unlike a working tutor profile.
if [ -n "$TEST_ADMIN_EMAIL" ] && [ -n "$TEST_ADMIN_PASSWORD" ]; then
    echo
    echo "== Test admin (role=owl): $TEST_ADMIN_EMAIL =="
    if WP user get "$TEST_ADMIN_EMAIL" --field=ID >/dev/null 2>&1; then
        echo "  exists -- ensuring role=owl and password matches .env"
        WP user set-role "$TEST_ADMIN_EMAIL" owl
        WP user update "$TEST_ADMIN_EMAIL" --user_pass="$TEST_ADMIN_PASSWORD" >/dev/null
    else
        echo "  missing -- creating fresh"
        WP user create "$TEST_ADMIN_EMAIL" "$TEST_ADMIN_EMAIL" \
            --role=owl \
            --user_pass="$TEST_ADMIN_PASSWORD" \
            --display_name="Test Admin"
    fi
    WP user get "$TEST_ADMIN_EMAIL" --fields=ID,user_login,roles
else
    echo
    echo "(TEST_ADMIN_EMAIL/PASSWORD not set in .env -- skipping admin fixture check)"
fi

echo
echo "== Blog video_id (test_video_object_json_ld) =="
if WP post get 194262 --field=ID >/dev/null 2>&1; then
    WP post meta update 194262 video_id "0UDU0j7Vd5w" >/dev/null
    echo "  set video_id on post 194262"
else
    echo "  post 194262 not found -- pick a current recent post and update this script" >&2
fi

echo
echo "Done. Add more fixture accounts to this script as they're found to need it."
