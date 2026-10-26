import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { saveLearningState } from '../src/progress.mjs';
export const basic = { sessionId: 'sample', topic: 'Synthetic', goal: 'Test only', phase: 'build', nextStep: 'Next', currentStep: 'Current', route: ['One', 'Two'] };
export const answer = { format: 'prediction', outcome: 'accurate', response: '  Actual supplied response\n', task: { prompt: 'Synthetic task', format: 'prediction', taskId: 'synthetic-task', rubricVersion: 'test-v1' } };
export async function fixture(t, { profile = false, state = {}, now } = {}) {
  const temporary = await realpath(await mkdtemp(join(tmpdir(), 'loom-v2-test-')));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const base = join(temporary, 'workspace');
  const exported = join(temporary, 'export');
  await mkdir(base); await mkdir(exported);
  const stage = join(exported, 'Current_Stage.md');
  if (profile) {
    await mkdir(join(base, '.concept-loom'));
    const config = { schemaVersion: 1, primarySessionId: 'sample', allowedSessionIds: ['sample'], notebookRoots: ['progress'],
      allowedExports: [stage], projections: { sessionId: 'sample', notebookPath: 'progress/notebook.md', stagePath: stage, stageIsExport: true }, ...profile };
    await writeFile(join(base, '.concept-loom/project.json'), JSON.stringify(config));
    await writeFile(stage, '---\nstatus: in-progress\ndate: 2000-01-01\ntype: plan\n---\n\n```table-of-contents\nincludeLinks: true\n```\n\n# Текущий фокус\n\nPreserve this old paragraph and [[Existing_Link]].\n');
  }
  const initial = await saveLearningState(base, { ...basic, ...state }, now ? { now } : {});
  return { base, temporary, stage, state: initial };
}
