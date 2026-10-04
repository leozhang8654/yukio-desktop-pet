import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { randomUUID } from 'node:crypto';

export const defaultRoot = process.env.YUKIO_ANSWER_BRIDGE_DIR || path.join(os.homedir(), 'Library/Application Support/YukioPlayer/answers');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function read(file) { try { return JSON.parse(await fs.readFile(file, 'utf8')); } catch { return null; } }
async function write(file, value) {
  const temporary = `${file}.${randomUUID()}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value), { mode: 0o600 });
  await fs.rename(temporary, file);
}
export function pendingQuestion(manager, session) {
  const entry = manager.getSession(session);
  if (entry?.status !== 'waiting_for_user' || entry.askPermissions?.length) return null;
  const messages = manager.listSessionMessages(session);
  // A newer user message supersedes the old tool question.
  for (const message of [...messages].reverse()) {
    if (message.role === 'user') return null;
    if (message.role !== 'tool' || message.visible === false) continue;
    let output; try { output = JSON.parse(message.content); } catch { continue; }
    if (output?.awaitUserResponse !== true || output.metadata?.kind !== 'ask_user_question') continue;
    const questions = output.metadata.questions;
    if (!Array.isArray(questions) || !questions.length || questions.some(q => typeof q.question !== 'string' || !q.question.trim())) return null;
    if (new Set(questions.map(q => q.question)).size !== questions.length) return null;
    return { session, callID: message.id, questions };
  }
  return null;
}
export function formatAnswers(questions, answers) {
  const clean = s => s.replace(/\s+/g, ' ').trim();
  return [`Questions ${questions.length}/${questions.length} answered`, ...questions.flatMap((q, i) => [` - ${clean(q.question)}`, `   answer: ${clean(answers[i])}`])].join('\n');
}
export async function answerPending(manager, pending, {root = defaultRoot, timeoutMs = 570000, signal} = {}) {
  const listener = path.join(root, 'listener-deepseek');
  try {
    const stat = await fs.stat(listener);
    const pid = Number(await fs.readFile(listener, 'utf8'));
    if (Date.now() - stat.mtimeMs > 5000 || !Number.isInteger(pid) || pid <= 0) return false;
    process.kill(pid, 0);
  } catch { return false; }
  const id = randomUUID(), dir = path.join(root, id);
  await fs.mkdir(dir, {recursive: true, mode: 0o700});
  const started = Date.now();
  await write(path.join(dir, 'request.json'), {
    provider: 'deepseek', id, session: pending.session, callID: pending.callID,
    pid: process.pid, createdAt: started, expiresAt: started + timeoutMs,
    questions: pending.questions.map(q => ({text: q.question, header: q.header || null, multiSelect: !!q.multiSelect,
      options: (q.options || []).map(o => ({label: typeof o === 'string' ? o : o.label, detail: o.description || null}))}))
  });
  const answers = [];
  try {
    while (!signal?.aborted && Date.now() - started < timeoutMs) {
      const current = pendingQuestion(manager, pending.session);
      if (current?.callID !== pending.callID) return false;
      try { if (Date.now() - (await fs.stat(listener)).mtimeMs > 5000) return false; } catch { return false; }
      for (let i = 0; i < pending.questions.length; i++) {
        if (answers[i]) continue;
        const answer = await read(path.join(dir, `answer-${i}.json`));
        if (typeof answer !== 'string' || !answer.trim() || Buffer.byteLength(answer) > 65536) continue;
        answers[i] = answer;
        // Partial receipt advances the card. The last answer requires a saved model input.
        if (i < pending.questions.length - 1) await write(path.join(dir, `receipt-${i}.json`), answer);
      }
      if (pending.questions.every((_, i) => answers[i])) {
        const text = formatAnswers(pending.questions, answers);
        let failure;
        const execution = Promise.resolve(manager.replySession(pending.session, {text, imageUrls: [], isAnswers: true, planMode: !!manager.getSession(pending.session)?.planMode})).catch(error => { failure = error; });
        const deadline = Date.now() + 2500;
        while (Date.now() < deadline) {
          const accepted = manager.listSessionMessages(pending.session).some(m => m.role === 'user' && m.content === text && m.meta?.isAnswers === true);
          if (accepted) {
            await write(path.join(dir, `receipt-${answers.length - 1}.json`), answers.at(-1));
            // Keep model execution alive without blocking the answer receipt.
            void execution;
            return true;
          }
          if (failure) throw failure;
          await sleep(30);
        }
        return false;
      }
      await sleep(100);
    }
    return false;
  } finally { await fs.writeFile(path.join(dir, 'done'), '', {mode: 0o600}); }
}

/** Attach to an owned Deep Code SessionManager. Never manipulates another terminal. */
export function attachYukioAnswers(manager, options = {}) {
  const controller = new AbortController();
  let busy = false;
  const timer = setInterval(async () => {
    if (busy || controller.signal.aborted) return;
    const session = manager.getActiveSessionId();
    const pending = session && pendingQuestion(manager, session);
    if (!pending) return;
    busy = true;
    try { await answerPending(manager, pending, {...options, signal: controller.signal}); }
    catch (error) { options.onError?.(error); }
    finally { busy = false; }
  }, 250);
  return () => { clearInterval(timer); controller.abort(); };
}
