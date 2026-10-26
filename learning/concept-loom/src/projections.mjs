import { dataPath, notebookPath, projectConfig } from './paths.mjs';
import { atomicWrite, readOptional } from './storage.mjs';
import { hash } from './validation.mjs';

const begin = '<!-- concept-loom:current-stage:begin -->';
const end = '<!-- concept-loom:current-stage:end -->';
const toc = '```table-of-contents\ntitle: \nstyle: nestedList\nminLevel: 0\nmaxLevel: 0\ninclude: \nexclude: \nincludeLinks: true\nhideWhenEmpty: false\ndebugInConsole: false\n```';
function code(value) {
  const text = String(value);
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map(item => item.length));
  const fence = '`'.repeat(Math.max(3, longest + 1));
  return `${fence}text\n${text}\n${fence}`;
}
export function eventNote(event) {
  const marker = `<!-- concept-loom:event=${event.eventId};revision=${event.revision} -->`;
  if (event.kind === 'import-baseline') return `${marker}\n\n> [!note] Историческое состояние перенесено в журнал\n> Ревизия ${event.revision}. Источник — существующая запись ConceptLoom; новых проверок и отметок освоения не добавлено.\n>\n> Текущий шаг: ${event.baseline.currentStep ?? 'не указан'}\n>\n> Продолжение: ${event.baseline.nextStep}\n`;
  const attempt = Object.values(event.evidenceUpdates ?? {}).flatMap(update => update.historyAppend ?? update.replacement?.history?.slice(-1) ?? [])[0];
  let body;
  if (attempt) {
    const help = { unknown: 'помощь не указана', none: 'заявлена работа без подсказки', hint: 'с подсказкой', explanation: 'после объяснения', solution: 'после готового решения' }[attempt.assistance.status];
    const parts = [`${attempt.task.prompt ?? 'Задание из внешней оценки'}\n\nОтвет:\n${code(attempt.response ?? attempt.selected?.join(', ') ?? '')}`];
    for (const observation of attempt.observations ?? []) parts.push(`${observation.kind} (${observation.source}):\n${code(observation.text)}`);
    parts.push(`Оценка наставника: ${attempt.outcome}; ${help}. ${attempt.delayedReview ? 'Отложенная проверка по текущей политике.' : 'Отложенная устойчивость этой попыткой не подтверждается.'}`);
    if (attempt.confidence !== undefined) parts.push(`Заявленная уверенность: ${attempt.confidence}/100; это не измерение освоения.`);
    if (attempt.note) parts.push(attempt.note);
    parts.push(`Продолжение: ${event.changes.nextStep ?? 'сохранённый следующий шаг'}`);
    body = parts.join('\n\n');
  } else {
    const parts = [];
    const response = event.changes.latestLearnerResponse;
    if (response?.text) parts.push(`Ответ ученика:\n${code(response.text)}`);
    for (const observation of response?.observations ?? []) parts.push(`${observation.kind}:\n${code(observation.text)}`);
    if (event.changes.currentStep) parts.push(`Текущий шаг: ${event.changes.currentStep}`);
    if (event.changes.nextStep) parts.push(`Продолжение: ${event.changes.nextStep}`);
    if (event.kind === 'route-approved') parts.unshift('Зафиксировано согласие на указанную версию маршрута; это не проверка знаний.');
    if (event.kind === 'lesson-start') parts.unshift('Занятие возобновлено с сохранённого шага.');
    if (!parts.length) parts.push('Обновлены служебные данные состояния; новая демонстрация знания не заявлялась.');
    body = parts.join('\n\n');
  }
  return `${marker}\n\n> [!note] ${event.recordedAt.slice(0, 10)}\n>\n${body.split('\n').map(line => `> ${line}`).join('\n')}\n`;
}
export function stageBlock(state, environment = {}) {
  const recordedAt = Date.parse(state.migratedAt) > Date.parse(state.updatedAt) ? state.migratedAt : state.updatedAt;
  const lab = environment.labCommandExecutor === 'learner' ? `Лаборатория: ${environment.lab}. Команды выполняет ученик; существование временных файлов проверяется перед опытом.` : 'Условия опытов и исполнителя команд определяют правила проекта.';
  return `${begin}\n# Текущий фокус\n\nЗапись обновлена: ${recordedAt.slice(0, 10)}. Состояние занятия: ${state.updatedAt.slice(0, 10)}. Ревизия ConceptLoom: ${state.revision}.\n\n${state.currentStep ?? 'Текущий шаг пока не указан.'}\n\nСледующее действие: ${state.nextStep}\n\n${state.activeLesson?.status === 'paused' ? 'Занятие приостановлено. ' : ''}Самостоятельность, помощь и воспроизведение спустя время учитываются раздельно. Открытые вопросы не меняют согласованный маршрут автоматически.\n\nПолные свидетельства — в журнале проекта. ${lab}\n${end}`;
}
function updateStage(existing, state, environment) {
  const block = stageBlock(state, environment);
  if (existing.includes(begin) || existing.includes(end)) {
    if (existing.split(begin).length !== 2 || existing.split(end).length !== 2 || existing.indexOf(end) < existing.indexOf(begin)) throw new Error('Current_Stage managed block is malformed; preserve the file and inspect it');
    return existing.slice(0, existing.indexOf(begin)) + block + existing.slice(existing.indexOf(end) + end.length);
  }
  let prefix = '';
  let history = existing;
  const front = existing.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n/);
  if (front) { prefix = front[0]; history = history.slice(prefix.length); }
  else prefix = `---\nstatus: in-progress\ndate: ${state.updatedAt.slice(0, 10)}\ntype: plan\n---\n`;
  const table = history.match(/```table-of-contents[\s\S]*?\n```/);
  if (table) { prefix += `\n${table[0]}\n\n`; history = history.replace(table[0], ''); }
  else prefix += `\n${toc}\n\n`;
  const preserved = history.trim().replace(/^# Текущий фокус\s*\n/, '');
  return `${prefix}${block}\n${preserved ? `\n# Исторический контекст\n\nНиже сохранена прежняя запись. Её старые указания продолжения относятся к прошлым занятиям; актуальное действие указано выше.\n\n${preserved}\n` : ''}`;
}
function configured(base, id) {
  const profile = projectConfig(base);
  const projections = profile.projections;
  return projections && (!projections.sessionId || projections.sessionId === id) ? projections : null;
}
export async function inspectProjections(base, state, events) {
  const config = configured(base, state.sessionId);
  if (!config) return { enabled: false, issues: [] };
  const issues = [];
  const targets = {};
  for (const kind of ['notebook', 'stage']) {
    const requested = config[`${kind}Path`];
    if (!requested) continue;
    try {
      const path = notebookPath(base, requested, kind === 'stage' && config.stageIsExport ? 'export' : 'notebook');
      targets[kind] = path;
      const contents = await readOptional(path);
      if (contents === null) { issues.push({ kind: `${kind}-missing`, path }); continue; }
      if (kind === 'stage' && !contents.includes(stageBlock(state, projectConfig(base).environment))) issues.push({ kind: 'stage-out-of-sync', path, expectedRevision: state.revision });
      if (kind === 'notebook') {
        const missing = events.filter(event => !contents.includes(eventNote(event)));
        if (missing.length) issues.push({ kind: 'notebook-out-of-sync', path, events: missing.map(event => event.eventId) });
      }
    } catch (error) { issues.push({ kind: `${kind}-access-error`, requestedPath: requested, message: error.message }); }
  }
  return { enabled: true, revision: state.revision, targets, issues };
}
export async function syncProjections(base, state, events) {
  try {
    const config = configured(base, state.sessionId);
    if (!config) return { enabled: false, issues: [] };
    const failures = [];
    if (config.notebookPath) {
      try {
        const path = notebookPath(base, config.notebookPath);
        const existing = await readOptional(path) ?? '# Учебный журнал\n';
        const missing = events.filter(event => !existing.includes(`<!-- concept-loom:event=${event.eventId};`));
        if (missing.length) await atomicWrite(notebookPath(base, config.notebookPath), `${existing.trimEnd()}\n\n${missing.map(eventNote).join('\n')}`);
      } catch (error) { failures.push({ kind: 'notebook-write-error', requestedPath: config.notebookPath, message: error.message }); }
    }
    if (config.stagePath) {
      try {
        const purpose = config.stageIsExport ? 'export' : 'notebook';
        const path = notebookPath(base, config.stagePath, purpose);
        const existing = await readOptional(path) ?? '';
        let updated = updateStage(existing, state, projectConfig(base).environment);
        const recordedAt = Date.parse(state.migratedAt) > Date.parse(state.updatedAt) ? state.migratedAt : state.updatedAt;
        updated = updated.replace(/^(---\r?\n[\s\S]*?\n)date:[^\n]*(\n[\s\S]*?\n---)/, `$1date: ${recordedAt.slice(0, 10)}$2`);
        if (updated !== existing) await atomicWrite(notebookPath(base, config.stagePath, purpose), updated);
      } catch (error) { failures.push({ kind: 'stage-write-error', requestedPath: config.stagePath, message: error.message }); }
    }
    const health = await inspectProjections(base, state, events);
    const result = { ...health, issues: [...failures, ...health.issues], checkedAt: new Date().toISOString(), lastEventId: state.integrity?.eventId };
    await atomicWrite(dataPath(base, `projections/${state.sessionId}.json`), `${JSON.stringify(result, null, 2)}\n`);
    return result;
  } catch (error) { return { enabled: true, issues: [{ kind: 'projection-sync-error', message: error.message }], stateCommitted: true }; }
}
