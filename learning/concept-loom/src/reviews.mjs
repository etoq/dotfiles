export const DIMENSIONS = { choice: 'recognition', 'free-recall': 'recall', prediction: 'application', debugging: 'application', transfer: 'transfer', verification: 'verification' };
export function reviewOutcome(earlier, independent, lessonId, now, policy = {}) {
  const minimumDelay = (policy.minimumDelayHours ?? 24) * 3600000;
  const due = Number.isFinite(Date.parse(earlier.reviewAfter)) && Date.parse(earlier.reviewAfter) <= now.getTime();
  const elapsed = now.getTime() - Date.parse(earlier.lastSuccessfulRetrieval);
  const differentLesson = Boolean(earlier.lastSuccessfulLessonId) && earlier.lastSuccessfulLessonId !== lessonId;
  const delayedReview = independent && (earlier.independentSuccesses ?? 0) > 0 && due && elapsed >= minimumDelay && differentLesson;
  const reviewStreak = independent ? (earlier.reviewStreak ?? 0) + (delayedReview ? 1 : 0) : 0;
  const intervals = policy.intervalDays ?? [1, 3, 7, 14, 30];
  let reviewAfter;
  if (independent && !due && Number.isFinite(Date.parse(earlier.reviewAfter))) reviewAfter = earlier.reviewAfter;
  else {
    // A due date crossed during recent practice earns no spacing increase.
    const days = delayedReview ? intervals[Math.min(reviewStreak, intervals.length - 1)] : intervals[0];
    reviewAfter = new Date(now.getTime() + days * 86400000).toISOString();
  }
  return { delayedReview, reviewStreak, reviewAfter, elapsedSinceIndependentMs: Number.isFinite(elapsed) ? elapsed : null };
}
export function confidenceSignal(accurate, confidence) {
  if (confidence === undefined) return undefined;
  if (!accurate && confidence >= 75) return 'incorrect-high-confidence';
  if (accurate && confidence <= 40) return 'correct-low-confidence';
  return 'no-specific-signal';
}
