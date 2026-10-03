#!/usr/bin/env bash
# New-topic smoke test: deterministic records, exact per-partition oracle.
# No delete, reset-offsets, topic reuse, or existing-data mutation.
set -euo pipefail
export LC_ALL=C
export KAFKA_HEAP_OPTS='-Xms32m -Xmx256m'
bin=/opt/kafka/bin
bootstrap=kafka:19092
run_id=${1:-$(date -u +%Y%m%dT%H%M%SZ | tr '[:upper:]' '[:lower:]')-$$-$RANDOM}
if [[ $# -gt 1 || ! "$run_id" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]]; then
    printf 'Usage: bash /lab/scripts/01-smoke.sh [unique-lowercase-run-id, max 64 chars]\n' >&2
    exit 2
fi
topic="efl-smoke-${run_id}-events"
printf 'RUN_ID=%s\nTOPIC=%s\n' "$run_id" "$topic"
printf 'This run creates one NEW 3-partition / RF=1 topic and writes 12 records.\n'

# Fail closed on unreachable broker; a failed listing must not be treated as an empty cluster.
topic_list=$("$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --list)
if grep -Fqx "$topic" <<< "$topic_list"; then
    printf 'Refusing to reuse existing topic %s. Choose a new run ID; old evidence is preserved.\n' "$topic" >&2
    exit 3
fi
"$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --create --topic "$topic" \
    --partitions 3 --replication-factor 1 --config min.insync.replicas=1 \
    --config cleanup.policy=delete --config retention.ms=604800000 --config segment.bytes=16777216
"$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --describe --topic "$topic"

# For the 4.3.1 default keyed partitioner and these UTF-8 bytes, partition count 3:
# account-B -> 0, account-A -> 1, beta -> 2.
# BuiltInPartitioner.partitionForKey = toPositive(murmur2(serializedKey)) % 3.
# A partition-count or key-serializer change invalidates this oracle.
keys=(account-B account-A beta)
produce_fixture() {
    local seq partition key
    for seq in 1 2 3 4; do
        for partition in 0 1 2; do
            key=${keys[$partition]}
            printf '%s|id=%s-%s-%d;seq=%d;cents=%d\n' \
                "$key" "$run_id" "$key" "$seq" "$seq" "$((100 * partition + seq))"
        done
    done
}

# --sync makes each send failure observable in the producer exit status.
# Idempotence handles producer retry identity, not application replay across runs.
produce_fixture | "$bin/kafka-console-producer.sh" --bootstrap-server "$bootstrap" \
    --topic "$topic" --sync --reader-property parse.key=true --reader-property 'key.separator=|' \
    --command-property acks=all --command-property enable.idempotence=true \
    --command-property max.in.flight.requests.per.connection=1 \
    --command-property partitioner.ignore.keys=false --command-property linger.ms=0 \
    --command-property delivery.timeout.ms=30000 --command-property request.timeout.ms=10000 \
    --command-property max.block.ms=30000 --command-property "client.id=efl-smoke-${run_id}"

expected_offsets=$(printf '%s:0:4\n%s:1:4\n%s:2:4\n' "$topic" "$topic" "$topic")
check_end_offsets() {
    local actual_offsets
    actual_offsets=$("$bin/kafka-get-offsets.sh" --bootstrap-server "$bootstrap" --topic "$topic" --time latest)
    actual_offsets=$(printf '%s\n' "$actual_offsets" | sort)
    if [[ "$actual_offsets" != "$expected_offsets" ]]; then
        printf 'FAIL: end offsets differ. Expected:\n%s\nActual:\n%s\n' "$expected_offsets" "$actual_offsets" >&2
        exit 4
    fi
}
check_end_offsets

# Direct assignment + disabled commits: this test does not advance a user's group offsets.
# Offset==record count holds ONLY for this new, nontransactional, un-compacted fixture.
for partition in 0 1 2; do
    key=${keys[$partition]}
    expected=$(for seq in 1 2 3 4; do
        printf 'Partition:%d|Offset:%d|%s|id=%s-%s-%d;seq=%d;cents=%d\n' \
            "$partition" "$((seq - 1))" "$key" "$run_id" "$key" "$seq" "$seq" "$((100 * partition + seq))"
    done)
    actual=$("$bin/kafka-console-consumer.sh" --bootstrap-server "$bootstrap" --topic "$topic" \
        --partition "$partition" --offset earliest --max-messages 4 --timeout-ms 15000 \
        --command-property enable.auto.commit=false --isolation-level read_committed \
        --formatter-property print.partition=true --formatter-property print.offset=true \
        --formatter-property print.key=true --formatter-property print.value=true \
        --formatter-property 'key.separator=|')
    printf '\n== Partition %d actual records ==\n%s\n' "$partition" "$actual"
    if [[ "$actual" != "$expected" ]]; then
        printf 'FAIL: partition %d exact oracle mismatch. Expected:\n%s\n' "$partition" "$expected" >&2
        exit 5
    fi
done
check_end_offsets
printf '\nPASS: 12 exact records; three partitions; per-key seq 1..4; offsets 0..3; total cents=1230.\n'
printf 'Retained topic: %s (7-day retention; no automatic deletion or offset reset by this script).\n' "$topic"
printf 'Observe with: bash /lab/scripts/02-observe.sh %s\n' "$topic"
printf 'This proves a bounded single-node fixture, not crash durability, replication, transactions, or end-to-end EOS.\n'
