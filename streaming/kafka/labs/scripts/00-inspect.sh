#!/usr/bin/env bash
# Read-only broker/controller observations. Run with bash inside apache/kafka:4.3.1.
set -euo pipefail
export LC_ALL=C
export KAFKA_HEAP_OPTS='-Xms32m -Xmx256m'
bin=/opt/kafka/bin
bootstrap=kafka:19092

printf '== Client/runtime identity ==\n'
"$bin/kafka-topics.sh" --version
java -version
id
printf '\n== Generated broker configuration (selected non-secret keys) ==\n'
grep -E '^(node.id|process.roles|controller.quorum.voters|controller.listener.names|listeners|advertised.listeners|inter.broker.listener.name|log.dirs|metadata.log.dir|min.insync.replicas|offsets.topic.replication.factor|transaction.state.log.replication.factor|transaction.state.log.min.isr)=' /opt/kafka/config/server.properties
printf '\n== KRaft storage identity ==\n'
"$bin/kafka-storage.sh" info -c /opt/kafka/config/server.properties
printf '\n== Reachable broker APIs (not an HA proof) ==\n'
"$bin/kafka-broker-api-versions.sh" --bootstrap-server "$bootstrap"
printf '\n== Metadata quorum status ==\n'
"$bin/kafka-metadata-quorum.sh" --bootstrap-server "$bootstrap" describe --status
printf '\n== Supported and finalized feature levels (read-only) ==\n'
"$bin/kafka-features.sh" --bootstrap-server "$bootstrap" describe
printf '\n== Topics ==\n'
"$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --list
printf '\n== Consumer groups (none is valid for a fresh lab) ==\n'
"$bin/kafka-consumer-groups.sh" --bootstrap-server "$bootstrap" --list
