// Offline teaching model. No SDK, DSN, network, credentials, or file writes.
// Deliberately balanced strata make weighting exact here, not in arbitrary samples.
import assert from 'node:assert/strict';

const strata = [
  { name: 'normal', size: 10_000, failures: 100, keepEvery: 10 },
  { name: 'critical', size: 1_000, failures: 200, keepEvery: 2 },
];
const population = strata.flatMap(({ name, size, failures, keepEvery }) =>
  Array.from({ length: size }, (_, i) => ({
    id: `${name}-${i}`,
    stratum: name,
    failed: i < failures,
    cause: i < failures ? `${name}-synthetic-bug` : null,
    retained: i % keepEvery === 0,
    designWeight: keepEvery,
  })),
);

const summarize = (rows, weighted = false) => {
  const requests = rows.reduce((n, row) => n + (weighted ? row.designWeight : 1), 0);
  const errors = rows.reduce((n, row) => n + (row.failed ? (weighted ? row.designWeight : 1) : 0), 0);
  return { requests, errors, errorRate: errors / requests };
};
const truth = summarize(population);
const sample = population.filter(row => row.retained);
const naive = summarize(sample);
const weighted = summarize(sample, true);
// A second loss mechanism selectively removes retained normal-stratum failures.
const afterLoss = sample.filter(row => !(row.stratum === 'normal' && row.failed));
const misweightedAfterLoss = summarize(afterLoss, true);
const distinctCauses = new Set(population.filter(row => row.failed).map(row => row.cause)).size;

assert.deepEqual([truth.requests, truth.errors], [11_000, 300]);
assert.deepEqual([naive.requests, naive.errors], [1_500, 110]);
assert.deepEqual(weighted, truth);
assert.notEqual(naive.errorRate, truth.errorRate);
assert.deepEqual([misweightedAfterLoss.requests, misweightedAfterLoss.errors], [10_900, 200]);
assert.notEqual(misweightedAfterLoss.errorRate, truth.errorRate);
assert.equal(distinctCauses, 2);
assert.equal(new Set(population.map(row => row.id)).size, population.length);

console.log(JSON.stringify({
  scope: 'OFFLINE MODEL ONLY: not Sentry ingestion, SDK sampling, billing, or UI validation',
  population: truth,
  retainedNaive: naive,
  idealStratifiedWeighting: weighted,
  weightingIgnoringAdditionalLoss: misweightedAfterLoss,
  distinctSyntheticCauses: distinctCauses,
  assertions: 'PASS',
}, null, 2));
