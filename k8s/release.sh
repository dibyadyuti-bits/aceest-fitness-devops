#!/usr/bin/env bash
# ACEest Fitness & Gym - Kubernetes releases with five deployment strategies.
#
#   k8s/release.sh deploy   <strategy> <image> [baseline-image]
#   k8s/release.sh smoke    <strategy> [expected-version]
#   k8s/release.sh promote  <strategy>
#   k8s/release.sh rollback <strategy>
#   k8s/release.sh status   [strategy]
#   k8s/release.sh traffic  <strategy> [requests]
#
# strategy: rolling | blue-green | canary | ab-testing | shadow
#
# Every strategy runs in its own namespace (aceest-<strategy>) and is served by the NGINX
# ingress under /<strategy>/, so all five can run side by side on one Minikube cluster.
#
#   rolling     new pods replace old ones one at a time (maxSurge 1, maxUnavailable 0)
#   blue-green  new version goes to the idle colour, is smoke-tested, then the live Service
#               is switched to it; the old colour keeps running for an instant rollback
#   canary      CANARY_WEIGHT % (default 20) of requests go to the new version
#   ab-testing  variant B (new) only for requests with 'X-Variant: B' or cookie variant=always
#   shadow      users are served by the primary; every request is mirrored to the new version
#
# baseline-image: for canary / ab-testing / shadow, the version that keeps serving users
# the first time the strategy is deployed (default: the new image).
#
# Environment: CANARY_WEIGHT (20), ROLLOUT_TIMEOUT (180s),
#              ACEEST_URL (ingress address for 'traffic', default http://127.0.0.1)
set -euo pipefail

# Git Bash on Windows would rewrite arguments such as /rolling/health into Windows paths.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"
CANARY_WEIGHT="${CANARY_WEIGHT:-20}"
STRATEGIES="rolling blue-green canary ab-testing shadow"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

# ---------- helpers ----------

use_strategy() {
    case "${1:-}" in
        rolling|blue-green|canary|ab-testing|shadow) ;;
        *) die "unknown strategy '${1:-}' (expected one of: $STRATEGIES)" ;;
    esac
    STRATEGY="$1"
    NS="aceest-$1"
    PREFIX="/$1"
}

k() { kubectl -n "$NS" "$@"; }

# render FILE KEY=VALUE... : print FILE with each {{KEY}} replaced by VALUE.
render() {
    local file="$1" kv
    shift
    local expr=(-e 's/\r$//')
    for kv in "$@"; do
        expr+=(-e "s|{{${kv%%=*}}}|${kv#*=}|g")
    done
    sed "${expr[@]}" "$file"
}

apply() { render "$@" | k apply -f -; }

ensure_namespace() {
    kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl label namespace "$NS" app=aceest strategy="$STRATEGY" --overwrite >/dev/null
}

image_of() {  # image_of TRACK -> image of deployment aceest-TRACK, empty if it does not exist
    k get deployment "aceest-$1" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true
}

deploy_track() {  # deploy_track TRACK IMAGE REPLICAS
    log "Deployment aceest-$1: $2 ($3 replicas)"
    apply "$K8S_DIR/templates/deployment.yaml" TRACK="$1" IMAGE="$2" REPLICAS="$3" PREFIX="$PREFIX"
    k annotate deployment "aceest-$1" kubernetes.io/change-cause="image $2" --overwrite >/dev/null
}

service() {  # service NAME TRACK
    apply "$K8S_DIR/templates/service.yaml" NAME="$1" TRACK="$2"
}

wait_ready() {
    k rollout status "deployment/aceest-$1" --timeout="$ROLLOUT_TIMEOUT"
}

live_color() {
    k get service aceest-live -o jsonpath='{.spec.selector.track}' 2>/dev/null || true
}

# check SERVICE [EXPECTED_VERSION]
# Calls /health and /version of SERVICE from inside a running app pod (works without the
# ingress or a port-forward) and fails if the app is unhealthy or runs another version.
check() {
    local svc="$1" expected="${2:-}" pod
    pod="$(k get pods -l app=aceest --field-selector=status.phase=Running \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    [ -n "$pod" ] || die "no running aceest pod in $NS"
    k exec "$pod" -c app -- python -c '
import json, sys, time, urllib.error, urllib.request
base, expected = sys.argv[1], sys.argv[2]
for attempt in range(10):
    try:
        health = json.load(urllib.request.urlopen(base + "/health", timeout=5))
        break
    except OSError as exc:
        if attempt == 9:
            sys.exit("  %s: unreachable (%s)" % (base, exc))
        time.sleep(3)
try:
    info = json.load(urllib.request.urlopen(base + "/version", timeout=5))
except urllib.error.HTTPError:
    info = {"version": "unknown (no /version endpoint)", "variant": "-", "pod": "-"}
print("  %s: health=%s version=%s variant=%s pod=%s"
      % (base, health.get("status"), info["version"], info["variant"], info["pod"]))
if health.get("status") != "ok":
    sys.exit("  health check failed")
if expected and info["version"] != expected:
    sys.exit("  expected version %s, got %s" % (expected, info["version"]))
' "http://$svc$PREFIX" "$expected"
}

# ---------- deploy ----------

deploy_rolling() {
    local current
    current="$(image_of main)"
    [ -z "$current" ] || log "Rolling update $current -> $NEW_IMAGE"
    deploy_track main "$NEW_IMAGE" 3
    service aceest-main main
    apply "$K8S_DIR/rolling/ingress.yaml"
    wait_ready main
}

deploy_blue_green() {
    local live idle
    live="$(live_color)"
    if [ "$live" = blue ]; then idle=green; else idle=blue; fi
    log "Blue-green: live=${live:-none}, releasing $NEW_IMAGE on $idle"

    deploy_track "$idle" "$NEW_IMAGE" 2
    service aceest-blue blue
    service aceest-green green
    wait_ready "$idle"

    log "Smoke test on $idle before it gets any user traffic"
    check "aceest-$idle" "${EXPECTED_VERSION:-}"

    if [ -z "$live" ]; then
        service aceest-live "$idle"
    else
        log "Switching live traffic $live -> $idle"
        k patch service aceest-live --type merge \
            -p "{\"spec\":{\"selector\":{\"app\":\"aceest\",\"track\":\"$idle\"}}}"
    fi
    k annotate service aceest-live aceest/previous-color="${live:-}" --overwrite >/dev/null
    apply "$K8S_DIR/blue-green/ingress.yaml"
}

# canary, A/B and shadow: a baseline track keeps serving users, a second track gets the
# new image and a slice / a segment / a mirrored copy of the traffic.
deploy_pair() {  # deploy_pair BASE_TRACK NEW_TRACK
    local base_image
    base_image="$(image_of "$1")"
    deploy_track "$1" "${base_image:-$BASELINE_IMAGE}" 2
    deploy_track "$2" "$NEW_IMAGE" 1
    service "aceest-$1" "$1"
    service "aceest-$2" "$2"
    wait_ready "$1"
    wait_ready "$2"
}

cmd_deploy() {
    [ $# -ge 2 ] || usage
    use_strategy "$1"
    NEW_IMAGE="$2"
    BASELINE_IMAGE="${3:-$2}"
    ensure_namespace
    case "$STRATEGY" in
        rolling)    deploy_rolling ;;
        blue-green) deploy_blue_green ;;
        canary)
            deploy_pair stable canary
            apply "$K8S_DIR/canary/ingress.yaml"          # main ingress before the canary one
            apply "$K8S_DIR/canary/ingress-canary.yaml" WEIGHT="$CANARY_WEIGHT"
            log "Canary: ${CANARY_WEIGHT}% of $PREFIX/ traffic goes to $NEW_IMAGE" ;;
        ab-testing)
            deploy_pair a b
            apply "$K8S_DIR/ab-testing/ingress.yaml"
            apply "$K8S_DIR/ab-testing/ingress-b.yaml"
            log "A/B: 'X-Variant: B' header or cookie variant=always gets $NEW_IMAGE" ;;
        shadow)
            deploy_pair primary shadow
            apply "$K8S_DIR/shadow/ingress.yaml"
            log "Shadow: every $PREFIX/ request is mirrored to $NEW_IMAGE" ;;
    esac
    log "Deployed $NEW_IMAGE ($STRATEGY, namespace $NS)"
    k get deployments,services,ingress -o wide
}

# ---------- smoke test ----------

cmd_smoke() {
    [ $# -ge 1 ] || usage
    use_strategy "$1"
    local expected="${2:-}"
    log "Smoke test: $STRATEGY"
    case "$STRATEGY" in
        rolling)    check aceest-main "$expected" ;;
        blue-green) check aceest-live "$expected" ;;
        canary)     check aceest-stable; check aceest-canary "$expected" ;;
        ab-testing) check aceest-a; check aceest-b "$expected" ;;
        shadow)     check aceest-primary; check aceest-shadow "$expected" ;;
    esac
    echo "  smoke test passed"
}

# ---------- rollback / promote ----------

stop_track() {  # stop_track TRACK : take a track out of service
    k scale deployment "aceest-$1" --replicas=0
}

cmd_rollback() {
    [ $# -ge 1 ] || usage
    use_strategy "$1"
    log "Rolling back $STRATEGY"
    case "$STRATEGY" in
        rolling)
            k rollout undo deployment/aceest-main
            wait_ready main ;;
        blue-green)
            local live previous
            live="$(live_color)"
            previous="$(k get service aceest-live -o jsonpath='{.metadata.annotations.aceest/previous-color}' 2>/dev/null || true)"
            [ -n "$previous" ] || die "no previous colour recorded: nothing to roll back to"
            k scale deployment "aceest-$previous" --replicas=2
            wait_ready "$previous"
            k patch service aceest-live --type merge \
                -p "{\"spec\":{\"selector\":{\"app\":\"aceest\",\"track\":\"$previous\"}}}"
            k annotate service aceest-live aceest/previous-color="$live" --overwrite >/dev/null
            echo "  live traffic switched back $live -> $previous" ;;
        canary)
            k delete ingress aceest-canary --ignore-not-found
            stop_track canary ;;
        ab-testing)
            k delete ingress aceest-b --ignore-not-found
            stop_track b ;;
        shadow)
            # Users were never served by the shadow: stop mirroring and stop the pods.
            k annotate ingress aceest nginx.ingress.kubernetes.io/mirror-target- >/dev/null 2>&1 || true
            stop_track shadow ;;
    esac
    k get deployments -o wide
}

# Make the new version the only version: the baseline track takes the new image.
promote_pair() {  # promote_pair BASE_TRACK NEW_TRACK
    local image
    image="$(image_of "$2")"
    [ -n "$image" ] || die "aceest-$2 not found: deploy first"
    log "Promoting $image to aceest-$1"
    k set image "deployment/aceest-$1" app="$image"
    k annotate deployment "aceest-$1" kubernetes.io/change-cause="promoted $image" --overwrite >/dev/null
    wait_ready "$1"
    stop_track "$2"
}

cmd_promote() {
    [ $# -ge 1 ] || usage
    use_strategy "$1"
    case "$STRATEGY" in
        rolling)
            echo "rolling: nothing to promote, the update is already complete" ;;
        blue-green)
            local previous
            previous="$(k get service aceest-live -o jsonpath='{.metadata.annotations.aceest/previous-color}' 2>/dev/null || true)"
            if [ -n "$previous" ]; then stop_track "$previous"; fi
            echo "  $(live_color) stays live; ${previous:-no} idle colour scaled to 0" ;;
        canary)
            promote_pair stable canary
            k delete ingress aceest-canary --ignore-not-found ;;
        ab-testing)
            promote_pair a b
            k delete ingress aceest-b --ignore-not-found ;;
        shadow)
            promote_pair primary shadow
            k annotate ingress aceest nginx.ingress.kubernetes.io/mirror-target- >/dev/null 2>&1 || true ;;
    esac
}

# ---------- status / traffic ----------

cmd_status() {
    local s
    for s in ${1:-$STRATEGIES}; do
        use_strategy "$s"
        log "$STRATEGY (namespace $NS)"
        k get deployments -o custom-columns='NAME:.metadata.name,READY:.status.readyReplicas,WANTED:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image' 2>/dev/null \
            || echo "  not deployed"
        if [ "$STRATEGY" = blue-green ]; then echo "  live colour: $(live_color)"; fi
    done
}

# Send requests through the ingress and count which version / variant answered.
cmd_traffic() {
    [ $# -ge 1 ] || usage
    use_strategy "$1"
    local n="${2:-20}" url="${ACEEST_URL:-http://127.0.0.1}"
    local headers=()
    if [ "$STRATEGY" = ab-testing ] && [ -n "${AB_GROUP:-}" ]; then headers=(-H "X-Variant: $AB_GROUP"); fi
    log "$n requests to $url$PREFIX/version ${headers[*]:-}"
    for _ in $(seq 1 "$n"); do
        curl -s ${headers[@]+"${headers[@]}"} "$url$PREFIX/version" \
            | sed -n 's/.*"variant": *"\([^"]*\)".*"version": *"\([^"]*\)".*/\2 (\1)/p;
                      s/.*"error".*/1.x (no \/version endpoint)/p'
    done | sort | uniq -c
}

# ---------- main ----------

command="${1:-}"
[ -n "$command" ] || usage
shift
case "$command" in
    deploy)   cmd_deploy "$@" ;;
    smoke)    cmd_smoke "$@" ;;
    promote)  cmd_promote "$@" ;;
    rollback) cmd_rollback "$@" ;;
    status)   cmd_status "$@" ;;
    traffic)  cmd_traffic "$@" ;;
    *) usage ;;
esac
