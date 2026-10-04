#!/usr/bin/env node
// Builds an isolated copy of the official Deep Code CLI with one answer adapter.
// Does not overwrite the user's existing deepcode command or change permissions.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const revision = 'd370f3afe0391e22e22667479c5425efb3a14b5f';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = process.env.YUKIO_DEEPSEEK_RUNTIME || path.join(os.homedir(), 'Library/Application Support/YukioPlayer/deepseek-runtime');
function run(command, args, cwd = root) {
  const result = spawnSync(command, args, {cwd, stdio: 'inherit'});
  if (result.status !== 0) throw new Error(`${command} failed (${result.status})`);
}
if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node.js 22 or newer required');
await fs.mkdir(path.dirname(root), {recursive: true});
try { await fs.access(path.join(root, '.git')); }
catch { run('git', ['clone', 'https://github.com/lessweb/deepcode-cli.git', root], path.dirname(root)); }
const head = spawnSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).stdout.trim();
if (head !== revision) run('git', ['checkout', '--detach', revision]);
const app = path.join(root, 'packages/cli/src/ui/views/App.tsx');
let source = await fs.readFile(app, 'utf8');
if (!source.includes('attachYukioAnswers')) {
  const marker = '    });\n  }, [projectRoot]);';
  if (source.split(marker).length !== 2) throw new Error('Unsupported Deep Code App.tsx layout');
  source = 'import { attachYukioAnswers } from "../core/yukio-answer-bridge.mjs";\n' + source.replace(marker, marker + '\n\n  useEffect(() => attachYukioAnswers(sessionManager), [sessionManager]);');
  await fs.writeFile(app, source);
}
await fs.copyFile(path.join(here, 'bridge.mjs'), path.join(root, 'packages/cli/src/ui/core/yukio-answer-bridge.mjs'));
run('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund']);
run('npm', ['run', 'bundle']);
const launcher = path.join(root, 'yukio-deepseek');
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
await fs.writeFile(launcher, '#!/bin/sh\nexec ' + quote(process.execPath) + ' ' + quote(path.join(root, 'packages/cli/dist/cli.js')) + ' "$@"\n', {mode: 0o755});
console.log('\nInstalled isolated CLI with Yukio background answers:\n' + launcher);
