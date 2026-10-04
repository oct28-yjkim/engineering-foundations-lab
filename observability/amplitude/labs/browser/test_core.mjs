// Node built-in runner only. SDK doubles are not real Amplitude validation.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { approvedTarget, sdkOptions, MemoryStorage, LabController, SDK_URL } from './core.mjs';

const target = { hostname: '127.0.0.1', label: 'lab-training', confirmation: 'lab-training',
  region: 'us', key: 'synthetic-key-12345', approved: true };
function setup() {
  const entries = [], sent = [];
  let user, device = 'synthetic-device', session = 1000, optOut = false, id = 0, elapsed = 0;
  const client = {
    getUserId: () => user, getDeviceId: () => device, getSessionId: () => session, getOptOut: () => optOut,
    setUserId: v => { user = v; }, setSessionId: v => { session = v; }, setOptOut: v => { optOut = v; },
    reset: () => { user = undefined; device = 'new-device'; },
    track: (...args) => { sent.push(args); return { promise: Promise.resolve({ code: optOut ? 0 : 200,
      message: 'SECRET_DO_NOT_PRINT', event: { api_key: 'SECRET_DO_NOT_PRINT' } }) }; },
    flush: () => ({ promise: Promise.resolve() }),
  };
  const lab = new LabController(client, { runId: 'a'.repeat(32), emit: v => entries.push(v),
    now: () => 1000, monotonic: () => elapsed, uuid: () => `uuid-${++id}` });
  return { lab, client, sent, entries, advance: ms => { elapsed = ms; } };
}
test('all approvals precede SDK loading', () => {
  assert.equal(approvedTarget(target), true);
  for (const change of [{ hostname: 'company.example' }, { label: 'production' }, { confirmation: 'lab-other' },
    { region: '' }, { region: 'arbitrary-url' }, { key: '' }, { approved: false }]) {
    assert.throws(() => approvedTarget({ ...target, ...change }));
  }
});
test('pinned endpoint and disabled implicit collection', () => {
  assert.match(SDK_URL, /analytics-browser-2\.47\.2-min\.js\.gz$/);
  for (const region of ['us', 'eu']) {
    const opts = sdkOptions(region, 'synthetic-device');
    assert.equal(opts.autocapture, false);
    assert.equal(opts.defaultTracking, false);
    assert.equal(opts.fetchRemoteConfig, false);
    assert.equal(opts.remoteConfig.fetchRemoteConfig, false);
    assert.equal(opts.enableDiagnostics, false);
    assert.equal(opts.diagnosticsSampleRate, 0);
    assert.equal(opts.identityStorage, 'none');
    assert.equal(opts.flushMaxRetries, 0);
    assert.equal(opts.storageProvider instanceof MemoryStorage, true);
    assert.deepEqual(opts.trackingOptions, { ipAddress: false, language: false, platform: false });
    assert.equal(opts.serverUrl, region === 'us' ? 'https://api2.amplitude.com/2/httpapi' : 'https://api.eu.amplitude.com/2/httpapi');
  }
  assert.throws(() => sdkOptions('company-url', 'device'));
});
test('memory storage does not persist between instances', async () => {
  const first = new MemoryStorage(), second = new MemoryStorage();
  await first.set('events', [{ event_type: 'synthetic' }]);
  assert.equal((await first.get('events')).length, 1);
  assert.equal(await second.get('events'), undefined);
  await first.remove('events');
  assert.equal(await first.get('events'), undefined);
});
test('normal three-event workflow and redacted callback', async () => {
  const { lab, sent, entries } = setup();
  lab.login();
  for (const name of ['Product Viewed', 'Checkout Started', 'Purchase Completed']) lab.track(name);
  await lab.flush();
  assert.equal(sent.length, 3);
  assert.equal(new Set(sent.map(call => call[2].insert_id)).size, 3);
  assert.equal(sent[2][1].order_id, `efl-web-order-${'a'.repeat(32)}`);
  assert.equal(sent[0][1].source, 'efl-browser-sdk');
  assert.equal(sent[0][2].user_id, `efl-web-${'a'.repeat(32)}-user-a`);
  assert.equal(JSON.stringify(entries).includes('SECRET_DO_NOT_PRINT'), false);
  assert.equal(entries.filter(e => e.stage === 'sdk_callback').length, 3);
  assert.equal(entries.at(-1).chart_verified, false);
});
test('business duplicate differs from transport replay', () => {
  const { lab, sent } = setup();
  lab.track('Product Viewed', true);
  assert.equal(sent[0][1].lab_intent_id, sent[1][1].lab_intent_id);
  assert.notEqual(sent[0][2].insert_id, sent[1][2].insert_id);
  lab.replay();
  assert.deepEqual(sent[2], sent[1]);
  assert.equal(lab.calls, 3);
});
test('no replay across identity changes', () => {
  const { lab } = setup();
  assert.throws(() => lab.replay());
  lab.track('Product Viewed');
  lab.login();
  assert.throws(() => lab.replay(), /identity_changed/);
});
test('bad logout retains device and reset replaces it', () => {
  const { lab } = setup();
  lab.login();
  const before = lab.identity();
  const bad = lab.badLogout();
  assert.equal(bad.user_id, null);
  assert.equal(bad.device_id, before.device_id);
  const reset = lab.reset();
  assert.equal(reset.user_id, null);
  assert.notEqual(reset.device_id, before.device_id);
});
test('optout and explicit stop state are visible', () => {
  const { lab, client } = setup();
  assert.equal(lab.optOut(true).opt_out, true);
  assert.equal(lab.optOut(false).opt_out, false);
  lab.stop();
  assert.equal(client.getOptOut(), true);
  assert.throws(() => lab.track('Product Viewed'), /lab_stopped/);
  assert.throws(() => lab.optOut(false), /lab_stopped/);
});
test('twenty-call and elapsed-time budgets', () => {
  const { lab, sent } = setup();
  for (let i = 0; i < 20; i++) lab.track('Product Viewed');
  assert.throws(() => lab.track('Product Viewed'), /track_budget/);
  assert.equal(sent.length, 20);
  const timed = setup();
  timed.advance(300000);
  assert.throws(() => timed.lab.track('Product Viewed'), /time_budget/);
  assert.equal(timed.sent.length, 0);
  assert.equal(timed.client.getOptOut(), true);
});
test('arbitrary events and malformed run IDs rejected', () => {
  assert.throws(() => setup().lab.track('Real Customer Email'));
  assert.throws(() => new LabController({}, { runId: 'real-user@example.com' }));
});
test('static page has no eager external script, secret URL, or inline code', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const app = await readFile(new URL('./app.mjs', import.meta.url), 'utf8');
  assert.equal(/<script[^>]+src=["']https:/i.test(html), false);
  assert.match(html, /type="password"/);
  assert.match(html, /form-action 'none'/);
  assert.equal(app.indexOf('approvedTarget(target)') < app.indexOf('await loadSdk()'), true);
  assert.equal(/localStorage|sessionStorage|console\./.test(app), false);
  assert.match(app, /field\('key'\)\.value = ''/);
});
