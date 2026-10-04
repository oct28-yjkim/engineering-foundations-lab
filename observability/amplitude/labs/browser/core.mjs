// Real SDK adapter. No network or SDK import on module load; tests inject a double.
export const SDK_VERSION = '2.47.2';
export const SDK_URL = 'https://cdn.amplitude.com/libs/analytics-browser-2.47.2-min.js.gz';
export const MAX_TRACK_CALLS = 20;
export const MAX_ELAPSED_MS = 300_000;
const EVENTS = new Set(['Product Viewed', 'Checkout Started', 'Purchase Completed']);

export function approvedTarget({ hostname, label, confirmation, region, key, approved }) {
  if (!['localhost', '127.0.0.1'].includes(hostname)) throw new Error('localhost_only');
  if (!/^lab-[a-z0-9-]{1,50}$/.test(label) || confirmation !== label) throw new Error('test_label_mismatch');
  if (!['us', 'eu'].includes(region)) throw new Error('select_region');
  if (typeof key !== 'string' || !/^[A-Za-z0-9_-]{10,256}$/.test(key)) throw new Error('invalid_test_key_shape');
  if (approved !== true) throw new Error('explicit_approval_required');
  return true;
}

export class MemoryStorage {
  constructor() { this.values = new Map(); }
  async isEnabled() { return true; }
  async get(key) { return this.values.get(key); }
  async set(key, value) { this.values.set(key, structuredClone(value)); }
  async remove(key) { this.values.delete(key); }
  async reset() { this.values.clear(); }
  async getRaw(key) { const value = await this.get(key); return value === undefined ? undefined : JSON.stringify(value); }
}

export function sdkOptions(region, deviceId) {
  if (!['us', 'eu'].includes(region)) throw new Error('select_region');
  return {
    serverZone: region.toUpperCase(),
    serverUrl: region === 'eu' ? 'https://api.eu.amplitude.com/2/httpapi' : 'https://api2.amplitude.com/2/httpapi',
    autocapture: false, defaultTracking: false,
    fetchRemoteConfig: false, remoteConfig: { fetchRemoteConfig: false },
    enableDiagnostics: false, diagnosticsSampleRate: 0,
    identityStorage: 'none', storageProvider: new MemoryStorage(),
    cookieOptions: { upgrade: false },
    trackingOptions: { ipAddress: false, language: false, platform: false },
    transport: 'fetch', flushQueueSize: 10, flushIntervalMillis: 5000, flushMaxRetries: 0,
    deviceId, optOut: false, logLevel: 0,
    loggerProvider: { enable() {}, disable() {}, error() {}, warn() {}, log() {}, debug() {} },
  };
}

export class LabController {
  constructor(client, { runId, emit, now = Date.now, monotonic = () => performance.now(), uuid = () => crypto.randomUUID() }) {
    if (!/^[0-9a-f]{32}$/.test(runId)) throw new Error('invalid_run_id');
    this.client = client;
    this.runId = runId;
    this.emit = emit;
    this.now = now;
    this.monotonic = monotonic;
    this.uuid = uuid;
    this.started = monotonic();
    this.calls = 0;
    this.last = null;
    this.stopped = false;
    this.emit({ stage: 'ready', run_id: runId, source: 'efl-browser-sdk', sdk: SDK_VERSION });
  }
  guard(count = 0) {
    if (this.stopped) throw new Error('lab_stopped');
    if (this.monotonic() - this.started >= MAX_ELAPSED_MS) { this.stop(); throw new Error('time_budget_reached'); }
    if (this.calls + count > MAX_TRACK_CALLS) throw new Error('track_budget_reached');
  }
  identity() {
    this.guard();
    const result = { user_id: this.client.getUserId() ?? null, device_id: this.client.getDeviceId(),
      session_id: this.client.getSessionId(), opt_out: this.client.getOptOut() };
    this.emit({ stage: 'identity', ...result });
    return result;
  }
  login() { this.guard(); this.client.setUserId(`efl-web-${this.runId}-user-a`); return this.identity(); }
  badLogout() { this.guard(); this.client.setUserId(undefined); return this.identity(); }
  reset() { this.guard(); this.client.reset(); this.client.setSessionId(this.now()); return this.identity(); }
  optOut(value) { this.guard(); this.client.setOptOut(value); return this.identity(); }
  track(eventType, duplicate = false) {
    if (!EVENTS.has(eventType)) throw new Error('event_not_allowed');
    this.guard(duplicate ? 2 : 1);
    const intent = this.uuid();
    for (let copy = 0; copy < (duplicate ? 2 : 1); copy++) {
      const properties = { lab_run_id: this.runId, source: 'efl-browser-sdk', schema_version: 1,
        lab_intent_id: intent, product_id: 'synthetic-product-01' };
      if (eventType !== 'Product Viewed') properties.order_id = `efl-web-order-${this.runId}`;
      const options = { insert_id: this.uuid(), time: this.now(), session_id: this.client.getSessionId(),
        device_id: this.client.getDeviceId(), user_id: this.client.getUserId() };
      this.last = { eventType, properties, options };
      this.send(this.last, false);
    }
  }
  replay() {
    this.guard(1);
    if (!this.last) throw new Error('no_event_to_replay');
    // Refuse replay after identity changes: omitted user_id could be filled by SDK.
    if (this.last.options.user_id !== this.client.getUserId() || this.last.options.device_id !== this.client.getDeviceId()) {
      throw new Error('replay_identity_changed');
    }
    this.send(this.last, true);
  }
  send(saved, replay) {
    this.calls++;
    const sequence = this.calls;
    this.emit({ stage: 'track_called', call: sequence, event_type: saved.eventType,
      insert_id: saved.options.insert_id, intent_id: saved.properties.lab_intent_id,
      time: saved.options.time, user_id: saved.options.user_id ?? null,
      device_id: saved.options.device_id, replay, opt_out: this.client.getOptOut() });
    const promise = this.client.track(saved.eventType, structuredClone(saved.properties), structuredClone(saved.options)).promise;
    Promise.resolve(promise).then(result => {
      // Never print result.event, message, config, or raw errors (they may contain keys/payloads).
      this.emit({ stage: 'sdk_callback', call: sequence,
        code: Number.isInteger(result?.code) ? result.code : null, chart_verified: false });
    }, () => this.emit({ stage: 'sdk_callback_error', call: sequence, chart_verified: false }));
  }
  async flush() {
    this.guard();
    this.emit({ stage: 'flush_requested' });
    try { await this.client.flush().promise; this.emit({ stage: 'flush_resolved', chart_verified: false }); }
    catch { this.emit({ stage: 'flush_error', chart_verified: false }); }
  }
  stop() {
    this.stopped = true;
    this.client.setOptOut(true);
    this.emit({ stage: 'stopped', calls: this.calls, note: 'queued_and_inflight_not_cancelled_server_data_retained' });
  }
}
