import { SDK_URL, MAX_ELAPSED_MS, approvedTarget, sdkOptions, LabController } from './core.mjs';

const field = id => document.getElementById(id);
const output = field('output');
const lines = [];
function emit(value) {
  lines.push(JSON.stringify(value));
  output.textContent = lines.slice(-150).join('\n');
}
let controller;
let started = false;
function loadSdk() {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SDK_URL;
    script.referrerPolicy = 'no-referrer';
    script.onload = () => window.amplitude?.createInstance ? resolve(window.amplitude) : reject(new Error('sdk_unavailable'));
    script.onerror = () => reject(new Error('sdk_load_failed'));
    document.head.append(script);
  });
}
field('start').addEventListener('click', async () => {
  if (started) return;
  const target = { hostname: location.hostname, label: field('label').value, confirmation: field('confirm').value,
    region: field('region').value, key: field('key').value, approved: field('approved').checked };
  try { approvedTarget(target); }
  catch { emit({ stage: 'not_started', reason: 'check_localhost_label_region_key_and_explicit_approval' }); return; }
  if (location.protocol !== 'http:' || location.search || location.hash) {
    emit({ stage: 'not_started', reason: 'use_plain_localhost_http_without_query_or_fragment' }); return;
  }
  started = true;
  field('start').disabled = true;
  field('key').value = '';
  let client;
  try {
    const sdk = await loadSdk();
    client = sdk.createInstance();
    const runId = crypto.randomUUID().replaceAll('-', '');
    await client.init(target.key, undefined, sdkOptions(target.region, `efl-web-${runId}-device-a`)).promise;
    target.key = '';
    client.setSessionId(Date.now());
    controller = new LabController(client, { runId, emit });
    controller.identity();
    document.querySelectorAll('[data-action]').forEach(button => { button.disabled = false; });
    setTimeout(() => { if (controller && !controller.stopped) controller.stop(); }, MAX_ELAPSED_MS);
  } catch {
    target.key = '';
    client?.setOptOut(true);
    emit({ stage: 'initialization_failed', reason: 'inspect_local_network_without_sharing_key_or_raw_payload', retry: 'reload_after_diagnosis' });
  }
});
const actions = {
  login: () => controller.login(), view: () => controller.track('Product Viewed'),
  checkout: () => controller.track('Checkout Started'), purchase: () => controller.track('Purchase Completed'),
  duplicate: () => controller.track('Product Viewed', true), replay: () => controller.replay(),
  'bad-logout': () => controller.badLogout(), reset: () => controller.reset(),
  optout: () => controller.optOut(true), optin: () => controller.optOut(false),
  identity: () => controller.identity(), flush: () => controller.flush(), stop: () => controller.stop(),
};
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', async () => {
  if (!controller) return;
  try { await actions[button.dataset.action](); }
  catch { emit({ stage: 'action_stopped', reason: 'check_budget_last_event_identity_and_lab_state' }); }
}));
