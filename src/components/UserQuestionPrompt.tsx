import React, { useEffect, useMemo, useState } from 'react';
import { HelpCircle } from 'lucide-react';
import type { AgentQuestionInfo } from '../types/sessionTypes';

interface UserQuestionPromptProps {
  question: AgentQuestionInfo;
  onSubmit: (selectedOptionIds: string[], answerText?: string) => Promise<void> | void;
}

export const UserQuestionPrompt: React.FC<UserQuestionPromptProps> = ({
  question,
  onSubmit,
}) => {
  const [selectedOptionIds, setSelectedOptionIds] = useState<string[]>([]);
  const [answerText, setAnswerText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const canSubmit = useMemo(() => {
    return selectedOptionIds.length > 0 || answerText.trim().length > 0;
  }, [answerText, selectedOptionIds]);

  useEffect(() => {
    setSelectedOptionIds([]);
    setAnswerText('');
    setSubmitError(null);
  }, [question.question_id]);

  const metadata = question.question_metadata || {};
  const isStageGate = metadata.origin === 'stage_gate';
  const summary = typeof metadata.summary === 'string' ? metadata.summary : '';
  const recommendation = typeof metadata.recommendation === 'string' ? metadata.recommendation : '';
  const nextMode = typeof metadata.next_mode === 'string' ? metadata.next_mode : '';

  const toggleOption = (optionId: string) => {
    setSubmitError(null);
    setSelectedOptionIds((previous) => {
      if (!question.multi_select) {
        return [optionId];
      }
      if (previous.includes(optionId)) {
        return previous.filter((value) => value !== optionId);
      }
      return [...previous, optionId];
    });
  };

  const submitAnswer = async () => {
    if (!canSubmit || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await onSubmit(selectedOptionIds, answerText.trim() || undefined);
      setSelectedOptionIds([]);
      setAnswerText('');
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to submit answer');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-4 mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
      <div className="flex items-center gap-2 mb-2">
        <HelpCircle className="w-4 h-4 text-amber-400" />
        <p className="text-sm font-medium text-amber-300">
          {isStageGate ? 'Stage approval' : 'Agent Question'}
        </p>
        {isStageGate && nextMode && (
          <span className="rounded-md border border-amber-500/30 px-2 py-0.5 text-[11px] uppercase text-amber-200">
            {nextMode}
          </span>
        )}
      </div>

      <p className="text-sm text-fg mb-3">{question.question_text}</p>

      {isStageGate && (summary || recommendation) && (
        <div className="mb-3 grid gap-2 rounded-md border border-amber-500/20 bg-black/20 p-3 text-xs leading-5 text-amber-50/90">
          {summary && <p>{summary}</p>}
          {recommendation && <p className="text-amber-200">{recommendation}</p>}
        </div>
      )}

      {question.options.length > 0 && (
        <div className="space-y-2 mb-3">
          {question.options.map((option) => {
            const checked = selectedOptionIds.includes(option.id);
            return (
              <label
                key={option.id}
                className="flex items-center gap-2 text-sm text-fg cursor-pointer"
              >
                <input
                  type={question.multi_select ? 'checkbox' : 'radio'}
                  name={`question-${question.question_id}`}
                  checked={checked}
                  onChange={() => toggleOption(option.id)}
                  className="accent-amber"
                />
                <span>{option.label}</span>
              </label>
            );
          })}
        </div>
      )}

      <textarea
        value={answerText}
        onChange={(event) => {
          setAnswerText(event.target.value);
          setSubmitError(null);
        }}
        rows={2}
        placeholder={isStageGate ? 'Notes or constraints' : 'Optional additional context'}
        className="w-full mb-3 px-3 py-2 text-sm rounded-md bg-zinc-900 border border-zinc-700 text-fg placeholder:text-fg/40"
      />

      {submitError && <p className="mb-2 text-xs text-red-400">{submitError}</p>}

      <button
        type="button"
        onClick={submitAnswer}
        disabled={!canSubmit || isSubmitting}
        className="px-3 py-1.5 text-xs rounded-md bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Answer'}
      </button>
    </div>
  );
};
