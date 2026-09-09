#!/usr/bin/env bash
# Focused external-installer tests. No build, sudo, daemon or service mutation.
set -euo pipefail

test_root="$(cd "$(dirname "$0")/../.." && pwd)"
source "$test_root/scripts/pkg/install-local-direct.sh"

test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
test_log="$test_dir/actions"
test_release="$test_dir/release"
mkdir "$test_release"
cp /bin/true "$test_release/ryeos"
cp /bin/true "$test_release/ryeosd"

# Stub only this external bootstrap boundary. Missing artifacts must be refused
# before any authorization request; refused authorization must precede stop.
id() { printf '%s\n' 1000; }
sudo() { printf 'authorize\n' >> "$test_log"; return "$test_sudo_status"; }
stop_daemon_for_install() { printf 'stop\n' >> "$test_log"; }
ryeos_term_suspend() { :; }
ryeos_term_fail() { :; }

attempt_install() {
    preflight_host_install "$test_release" "$@" || return 1
    stop_daemon_for_install
}

test_sudo_status=0
if attempt_install ryeos absent; then
    echo 'missing required binary was accepted' >&2
    exit 1
fi
[[ ! -e "$test_log" ]]

test_sudo_status=1
if attempt_install ryeos ryeosd; then
    echo 'missing authorization was accepted' >&2
    exit 1
fi
[[ "$(<"$test_log")" == authorize ]]

: > "$test_log"
test_sudo_status=0
attempt_install ryeos ryeosd
[[ "$(<"$test_log")" == $'authorize\nstop' ]]

# Root already holds installation authority; do not require another prompt.
: > "$test_log"
id() { printf '%s\n' 0; }
attempt_install ryeos ryeosd
[[ "$(<"$test_log")" == stop ]]

# Guard the actual entrypoint ordering, not merely the mocked composition.
preflight_line="$(sed -n '/^preflight_host_install "\$target_dir"/=' "$test_root/scripts/pkg/install-local-direct.sh")"
stop_line="$(sed -n '/^    if stop_daemon_for_install; then/=' "$test_root/scripts/pkg/install-local-direct.sh")"
[[ -n "$preflight_line" && -n "$stop_line" && "$preflight_line" -lt "$stop_line" ]]

# The selected node must survive the installer -> sudo -> login shell boundary.
# Capture argv only; do not execute sudo or a child shell in these cases.
(
    invoking_user=selected_operator
    init_app_root="$test_dir/a selected node"
    id() { printf '%s\n' installer; }
    getent() { printf 'selected_operator:x:1000:1000::/unused:/bin/bash\n'; }
    run_timeout() { printf '%s\n' "$@" > "$test_log"; }
    ryeos_user 10 node status
    printf -v expected_command 'exec env %q ryeos node status' "RYEOS_APP_ROOT=$init_app_root"
    [[ "$(tail -n 1 "$test_log")" == "$expected_command" ]]
)
(
    invoking_user=selected_operator
    init_app_root="$test_dir/a selected node"
    id() { printf '%s\n' selected_operator; }
    run_timeout() { printf '%s\n' "$RYEOS_APP_ROOT" "$@" > "$test_log"; }
    ryeos_user 10 node status
    [[ "$(head -n 1 "$test_log")" == "$init_app_root" ]]
)

# Restore the real helper after the preflight composition stubs. Each stop
# case runs in a subshell because production die exits the installer.
source "$test_root/scripts/pkg/install-local-direct.sh"
ryeos_term_suspend() { :; }
ryeos_term_info() { :; }
ryeos_term_fail() { :; }
ryeos_user() {
    if [[ "$2" == stop ]]; then
        printf 'stop\n' >> "$test_log"
        return "$test_stop_result"
    fi
    return 98
}
ryeos_status_quick() {
    [[ "$test_probe_result" == 0 ]] || return "$test_probe_result"
    if [[ -s "$test_log" ]]; then
        [[ "$test_final_probe_result" == 0 ]] || return "$test_final_probe_result"
        printf '%s\n' "$test_after_status"
    else
        printf '%s\n' "$test_before_status"
    fi
}
kill() { printf 'raw-kill\n' >> "$test_log"; exit 99; }

test_probe_result=0
test_final_probe_result=0
test_stop_result=0
test_before_status=running
test_after_status='initialized, stopped — run: ryeos start'

# Exercise the actual installer caller. `return 1` means initially stopped;
# uncertainty must exit, not return and allow the enclosing if to continue.
replacement_boundary() (
    daemon_was_running=0
    if stop_daemon_for_install; then
        daemon_was_running=1
    fi
    printf 'replace restart=%s\n' "$daemon_was_running" >> "$test_log"
)
expect_refused_replacement() {
    : > "$test_log"
    if replacement_boundary; then
        echo 'unsafe lifecycle outcome allowed replacement' >&2
        exit 1
    fi
    [[ "$(<"$test_log")" == "${1:-}" ]]
}

test_before_status=running
test_after_status='initialized, stopped — run: ryeos start'
: > "$test_log"
replacement_boundary
[[ "$(<"$test_log")" == $'stop\nreplace restart=1' ]]

for test_before_status in 'initialized, stopped — run: ryeos start' 'not initialized — run: ryeos init'; do
    : > "$test_log"
    replacement_boundary
    [[ "$(<"$test_log")" == 'replace restart=0' ]]
done
for test_before_status in '' 'stale daemon metadata' 'unrecognized state'; do
    expect_refused_replacement
done
test_before_status=running
test_probe_result=1
expect_refused_replacement
test_probe_result=0
test_final_probe_result=1
expect_refused_replacement stop
test_final_probe_result=0
test_stop_result=1
expect_refused_replacement stop
test_stop_result=0
test_after_status=running
expect_refused_replacement stop
printf 'installer lifecycle preflight and shutdown refusal: passed\n'
