import type { Answer, Question } from "./types";

export const MBTI_QUESTION_VERSION = "mbti-chat-evidence-v4";
export const MBTI_SOURCES = [
  "https://www.myersbriggs.org/my-mbti-personality-type/the-mbti-preferences/",
  "https://www.themyersbriggs.com/en-US/Products-and-Services/Myers-Briggs",
] as const;

export interface PersonalityEvidence {
  EI: { E: number; I: number; insufficient: number };
  SN: { S: number; N: number; insufficient: number };
  TF: { T: number; F: number; insufficient: number };
  JP: { J: number; P: number; insufficient: number };
}
const OPTIONS = {
  EI: ["no energy preference shown", "outward interaction restores energy", "inward reflection restores energy"],
  SN: ["no information preference shown", "concrete facts and experience", "patterns and possibilities"],
  TF: ["no decision preference shown", "logical principles in decisions", "personal values and people's impact"],
  JP: ["no external-world preference shown", "structured closure and schedules", "flexible exploration of options"],
} as const;

export const PERSONALITY_QUESTIONS: Record<string, Question> = {
  mbti_scope: {
    type: "choice",
    instructions: "Across the TARGET sender's own messages, is there any repeated choice, reason, or interaction habit about energy, information, decisions, or planning? An explicit personality label is not required. Choose no preference pattern shown only for greetings, acknowledgements, or one isolated fact. Judge each axis separately; this summary must not erase a specific axis.",
    criteria: ["no preference pattern shown", "preference pattern shown"],
  },
  mbti_EI: {
    type: "choice",
    instructions: "How does the TARGET sender restore energy in their own messages? Outward: they start contact, talk ideas through with people, or sound energized by interaction. Inward: they step back to think alone, limit contact, or recover in quiet. One greeting or one long reply is not a pattern. When a side is shown, its score must exceed no energy preference shown. When neither side is shown, no energy preference shown must be highest.",
    criteria: [...OPTIONS.EI],
  },
  mbti_SN: {
    type: "choice",
    instructions: "How does the TARGET sender take in information? Concrete: they stay with facts, examples, and what already happened. Abstract: they connect ideas, ask what a pattern implies, or explore possibilities. One fact or one idea is not a pattern. When a side is shown, its score must exceed no information preference shown. When neither side is shown, no information preference shown must be highest.",
    criteria: [...OPTIONS.SN],
  },
  mbti_TF: {
    type: "choice",
    instructions: "What basis does the TARGET sender use when they give a reason? Principles: a consistent rule, tradeoff, or standard. Values: how people are affected or what matters to them. One emotion word is not a decision preference. When a side is shown, its score must exceed no decision preference shown. When neither side is shown, no decision preference shown must be highest.",
    criteria: [...OPTIONS.TF],
  },
  mbti_JP: {
    type: "choice",
    instructions: "How does the TARGET sender handle choices they can make? Closure: they decide, schedule, and narrow options themselves. Open: they keep alternatives, postpone, or revise while exploring. Finishing a task someone else assigned is not closure. When a side is shown, its score must exceed no external-world preference shown. When neither side is shown, no external-world preference shown must be highest.",
    criteria: [...OPTIONS.JP],
  },
};

function distribution<Left extends string, Right extends string>(
  answer: Answer | undefined,
  left: Left,
  right: Right,
  options: readonly [string, string, string],
): Record<Left | Right | "insufficient", number> | null {
  if (!answer || answer.type !== "choice") return null;
  const probabilities = answer.probabilities;
  if (!options.every((key) =>
    Number.isFinite(probabilities[key]) && probabilities[key] >= 0 && probabilities[key] <= 1
  )) return null;
  return { [left]: probabilities[options[1]], [right]: probabilities[options[2]], insufficient: probabilities[options[0]] } as Record<Left | Right | "insufficient", number>;
}

export function personalityEvidenceFromAnswers(answers: Record<string, Answer>): PersonalityEvidence | null {
  // Scope only asks whether any pattern exists. It must not discard an axis:
  // requiring an explicit self-label made every ordinary chat permanently insufficient.
  const EI = distribution(answers.mbti_EI, "E", "I", OPTIONS.EI);
  const SN = distribution(answers.mbti_SN, "S", "N", OPTIONS.SN);
  const TF = distribution(answers.mbti_TF, "T", "F", OPTIONS.TF);
  const JP = distribution(answers.mbti_JP, "J", "P", OPTIONS.JP);
  if (!EI || !SN || !TF || !JP) return null;
  const anySupported = EI.E > EI.insufficient || EI.I > EI.insufficient ||
    SN.S > SN.insufficient || SN.N > SN.insufficient ||
    TF.T > TF.insufficient || TF.F > TF.insufficient ||
    JP.J > JP.insufficient || JP.P > JP.insufficient;
  return anySupported ? { EI, SN, TF, JP } : null;
}
