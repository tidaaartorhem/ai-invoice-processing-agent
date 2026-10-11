// Verifies the Python pipeline's output bundle before every build.
// The pipeline itself runs separately (not from this script); this step
// only checks that web/public/*.json exist and parse as JSON.
// Fails loudly (non-zero exit) otherwise.
const fs = require('node:fs');
const path = require('node:path');

const webDir = path.resolve(__dirname, '..');
const publicDir = path.join(webDir, 'public');
const required = ['queue.json', 'duplicates.json', 'analytics.json', 'paste_samples.json', 'registers.json', 'meta.json'];

function fail(message) {
  console.error(`[prepare-public] ERROR: ${message}`);
  process.exit(1);
}

const missing = required.filter((f) => !fs.existsSync(path.join(publicDir, f)));
if (missing.length > 0) {
  fail(
    `missing required data files in web/public/: ${missing.join(', ')}. ` +
      'Run the Python data pipeline first, then rebuild.',
  );
}

for (const f of required) {
  try {
    JSON.parse(fs.readFileSync(path.join(publicDir, f), 'utf8'));
  } catch (err) {
    fail(`${f} exists but is not valid JSON: ${err.message}`);
  }
}

console.log(`[prepare-public] OK: ${required.join(', ')} present and valid in web/public/`);
