#!/usr/bin/env bash
# Read-only metadata, offsets and optional group observation; does not consume/commit.
set -euo pipefail
export LC_ALL=C
export KAFKA_HEAP_OPTS='-Xms32m -Xmx256m'
bin=/opt/kafka/bin
bootstrap=kafka:19092
topic=${1:-}
group=${2:-}
if [[ $# -gt 2 || ! "$topic" =~ ^efl-[A-Za-z0-9-]+$ ]]; then
    printf 'Usage: bash /lab/scripts/02-observe.sh efl-topic-name [efl-group-name]\n' >&2
    exit 2
fi
if [[ -n "$group" && ! "$group" =~ ^efl-[A-Za-z0-9-]+$ ]]; then
    printf 'Group names must use the efl- prefix and letters/digits/hyphens only.\n' >&2
    exit 2
fi
printf '== Topic metadata ==\n'
"$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --describe --topic "$topic"
printf '\n== Topic overrides ==\n'
"$bin/kafka-configs.sh" --bootstrap-server "$bootstrap" --entity-type topics --entity-name "$topic" --describe
printf '\n== Earliest offsets ==\n'
"$bin/kafka-get-offsets.sh" --bootstrap-server "$bootstrap" --topic "$topic" --time earliest
printf '\n== Latest offsets ==\n'
"$bin/kafka-get-offsets.sh" --bootstrap-server "$bootstrap" --topic "$topic" --time latest
printf '\n== Log directories (metadata only; no log file modification) ==\n'
"$bin/kafka-log-dirs.sh" --bootstrap-server "$bootstrap" --describe --topic-list "$topic"
if [[ -n "$group" ]]; then
    printf '\n== Group state and offsets (absence or no commit is a valid finding) ==\n'
    "$bin/kafka-consumer-groups.sh" --bootstrap-server "$bootstrap" --group "$group" --describe --state
    "$bin/kafka-consumer-groups.sh" --bootstrap-server "$bootstrap" --group "$group" --describe --offsets
fi
printf '\nOffset distances are not universally equal to record counts or business-processing lag.\n'
