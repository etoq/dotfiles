import { notebookPath, projectConfig, dataPath } from './paths.mjs';
import { atomicWrite, readOptional, withSessionLock } from './storage.mjs';
import { randomUUID } from 'node:crypto';

const permittedKinds = new Set(["learner", "guide", "prompt", "response", "insight", "diagram"]);

export function resolveNotebookPath(baseDirectory, requested = "learning-notes.md") {
  return notebookPath(baseDirectory, requested);
}

function blockFor(kind, body, title) {
  const text = String(body ?? "").trim();
  if (!text) throw new Error("body must be non-empty");
  const labels = {
    learner: "LEARNER",
    guide: "GUIDE",
    prompt: "CHECKPOINT",
    response: "CHECKPOINT RESULT",
    insight: "KEY CONNECTION",
    diagram: "DIAGRAM",
  };
  const heading = title?.trim() || labels[kind];
  return `> [!${kind === "response" ? "success" : kind === "prompt" ? "question" : "note"}] ${heading}\n>\n${text
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n")}`;
}

export async function beginNotebook(baseDirectory, input) {
  return withSessionLock(baseDirectory, projectConfig(baseDirectory).primarySessionId ?? 'notebooks', async () => {
    const destination = resolveNotebookPath(baseDirectory, input.path);
    const heading = typeof input.title === 'string' && input.title.trim() ? input.title.trim() : 'Learning session';
    const preamble = `# ${heading}\n\n_Created by Concept Loom on ${new Date().toISOString()}_\n`;
    const existing = await readOptional(destination);
    if (input.replace === true && existing) await atomicWrite(dataPath(baseDirectory, `backups/notebook-${randomUUID()}.md`), existing);
    if (input.replace === true || !existing?.trim()) await atomicWrite(resolveNotebookPath(baseDirectory, input.path), preamble);
    return destination;
  });
}

export async function addNotebookEntry(baseDirectory, input) {
  return withSessionLock(baseDirectory, projectConfig(baseDirectory).primarySessionId ?? 'notebooks', async () => {
    const destination = resolveNotebookPath(baseDirectory, input.path);
    const kind = String(input.kind ?? '');
    if (!permittedKinds.has(kind)) throw new Error(`kind must be one of: ${[...permittedKinds].join(', ')}`);
    const existing = await readOptional(destination);
    if (existing === null) throw new Error('start the notebook before adding a note');
    await atomicWrite(resolveNotebookPath(baseDirectory, input.path), `${existing.trimEnd()}\n\n${blockFor(kind, input.body, input.title)}\n`);
    return destination;
  });
}
