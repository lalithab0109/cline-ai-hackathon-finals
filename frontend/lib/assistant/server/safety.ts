/**
 * SERVER-ONLY safety layer. Defence in depth, not a single word list:
 *  1. Input intent classification (urgent symptoms / clinical-conclusion
 *     requests) -> FIXED responses; the model is never called for these.
 *  2. A strict system prompt (prompt.ts) that treats report + history as data.
 *  3. Output validation: rejects answers that state or deny diagnoses, give
 *     treatment/dosing, attach clinical severity to artificial bands, quote
 *     numbers that are not in the report, or leak instructions/secrets.
 *     Failing answers are replaced by a fixed fallback.
 */

import "server-only";

import { detectClinicalClaim } from "@/lib/assistant/server/claims/detect";

export const URGENT_HELP_RESPONSE =
  "I can't help with symptoms or emergencies. If you feel unwell — for example chest pain, " +
  "trouble breathing, fainting, severe bleeding, confusion, or thoughts of harming yourself — " +
  "please contact your local emergency number or go to the nearest emergency department now. " +
  "For non-urgent concerns, speak with a qualified doctor or health worker. " +
  "This app is a synthetic demonstration and cannot assess your health.";

export const CLINICAL_REFUSAL_RESPONSE =
  "I can't provide a diagnosis, treatment, medication or dosing advice, or say whether a " +
  "result is normal or abnormal. This report comes from a synthetic demonstration: any value " +
  "is simulated (either estimated by a model trained only on synthetic images, or a fixed mock " +
  "value), any category is a demonstration label (not a medical severity), and nothing here is clinically " +
  "validated. For questions about your health, please talk to a qualified clinician. I'm happy " +
  "to explain how this demonstration result was produced.";

export const SAFETY_FALLBACK_RESPONSE =
  "I couldn't produce an answer that stays within the limits of this synthetic demonstration, " +
  "so I've withheld it. I can explain how the result was calculated, what the image-quality " +
  "information means, what the artificial category represents, and why this report is not " +
  "medically validated.";

const norm = (s: string) => s.toLowerCase().replace(/[’‘]/g, "'").replace(/\s+/g, " ");

// ---- 1. input intent ----------------------------------------------------------------------------
const URGENT: RegExp[] = [
  /\b(chest|heart)\s+(pain|pressure|tight)/,
  /\b(can'?t|cannot|unable to|struggling to|hard to|difficulty)\s+breath/,
  /\bshort(ness)? of breath\b/,
  /\b(faint(ed|ing)?|pass(ed|ing) out|unconscious|seizure|convuls)/,
  /\b(severe|heavy|uncontrolled|won'?t stop)\s+(bleed|pain|headache)/,
  /\b(vomit(ing)?|cough(ing)?) (up )?blood\b/,
  /\b(suicid|kill myself|self[- ]harm|end my life|hurt myself)/,
  /\b(stroke|numb(ness)? (on|in) one side|slurred speech)/,
  /\b(emergency|ambulance|911|108|112)\b/,
  /\b(overdose|poison(ed|ing))\b/,
  /\bi (feel|am feeling|'m feeling) (very |really |extremely |so )?(dizzy|faint|sick|unwell|weak)\b/,
];

const DISEASE_IN =
  "(anemi|anaemi|diabet|kidney|renal|nephro|ckd|thalass|iron deficien|hypergly|hypogly|prediabet|albuminuri|proteinuri|disease|disorder|condition|illness|cancer|infection)";
const CLINICAL: RegExp[] = [
  new RegExp(`\\b(do|does|did|am|is|are|could|might|would|will)\\b[^?.!]{0,40}\\b(i|me|my|patient|person)\\b[^?.!]{0,40}${DISEASE_IN}`),
  new RegExp(`\\b(have|got|suffer|diagnos|test(ed)? positive|rule (in|out))\\w*\\b[^?.!]{0,40}${DISEASE_IN}`),
  new RegExp(`\\b(mild|moderate|severe|serious|dangerous|critical|life[- ]threatening)\\b[^?.!]{0,30}${DISEASE_IN}`),
  /\b(diagnos(e|is|ed|ing)|prognos)/,
  /\b(treat(ment|ing)?|cure|therap(y|ies)|prescri(be|ption)|medic(ine|ation)s?|drugs?|pills?|tablets?|supplements?|vitamins?|dos(e|age|ing)|injections?|transfusion|insulin|metformin|ferrous)\b/,
  /\bhow (much|many) (iron|mg|tablets?|pills?)\b/,
  /\bwhat (should|can|do) i (eat|take|do)\b/,
  /\b(diet|foods?)\b[^?.!]{0,30}\b(raise|increase|lower|reduce|improve|fix)/,
  /\b(is|am|are)\b[^?.!]{0,30}\b(this|it|my|i|result|value|level|number)\b[^?.!]{0,30}\b(normal|abnormal|healthy|unhealthy|low|high|dangerous|bad|good|worrying|concerning|serious)\b/,
  /\b(normal|healthy|reference|safe|target)\s+(range|level|value|limit|threshold)s?\b/,
  /\b(should i|do i need to|must i) (see|visit|go to|consult) (a |the )?(doctor|physician|hospital|clinic)/,
  /\bmean for my health\b/,
  /\b(am i|i am|i'm) (sick|ill|healthy|okay|ok|fine|at risk)\b/,
  /\b(risk|chance|likelihood|probability) (of|that i|i have)\b/,
];

export type InputIntent = "urgent" | "clinical" | "explain";

export function classifyQuestion(question: string): InputIntent {
  const q = norm(question);
  if (URGENT.some((r) => r.test(q))) return "urgent";
  if (CLINICAL.some((r) => r.test(q))) return "clinical";
  return "explain";
}

// ---- 3. output validation ----------------------------------------------------------------------
// Diagnosis / denial / severity / normal-range claims are judged per sentence and clause by
// detectClinicalClaim (claims/detect.ts). Treatment and leak checks below stay pattern-based:
// they must never be excused by negation ("do not stop taking your iron tablets" is still advice).
const OUT_TREATMENT: RegExp[] = [
  /\b(you should|i recommend|i suggest|consider|try) (taking|eating|starting|stopping|increasing|reducing)\b/,
  // Dose amounts ("65 mg", "2 tablets"); concentration units like mg/dL or mg/L are report values, not doses.
  /\b\d+(\.\d+)?\s?(mg|mcg|µg|iu|units?|tablets?|pills?)\b(?!\s*\/)/,
  /\b(take|start|begin|prescribe[ds]?)\b[^.]{0,30}\b(iron|supplements?|medications?|medicines?|insulin|metformin|tablets?|pills?|vitamins?)/,
  /\b(stop|stopping|continue|keep|skip|increase|decrease|reduce|double|change|adjust)\b[^.]{0,20}\b(taking|iron|supplements?|medications?|medicines?|insulin|metformin|tablets?|pills?|vitamins?|dose|dosage)\b/,
  /\b(eat|eating|drink|drinking|diet|foods?)\b[^.]{0,30}\b(iron|spinach|red meat|sugar|carbs?|protein|salt|raise|increase|lower|reduce|boost)\b/,
  // Referring someone to a clinician is allowed; personal medical instructions are not.
  /\b(you should|you need to|you must|i recommend|i suggest|i advise|my advice)\b[^.]{0,40}\b(treat\w*|medic\w*|eat|take|stop|start|supplement\w*)\b/,
  /\b(treat(ment|ed|ing)?|transfusion|prescri\w+|therap(y|ies))\b[^.]{0,30}\b(for|of|with|is|would|should|needed|recommended|required)\b/,
];
const OUT_LEAK: RegExp[] = [
  /\b(system prompt|developer message|my instructions (are|say)|ignore (all|the|previous) (instructions|rules))\b/i,
  /\b(jailbreak|dan mode|developer mode)\b/i,
  /<\s*\/?\s*(report_context|conversation|question|system)\s*>/i,
  /\b(sk|key|token)[-_][A-Za-z0-9_-]{16,}/i,
  /\bCLINE_API_KEY\b/i,
];

function addNumber(set: Set<string>, n: number) {
  if (!Number.isFinite(n)) return;
  for (const digits of [0, 1, 2, 3]) set.add(String(Number(n.toFixed(digits))));
  set.add(String(n));
}

/** Numbers the model may quote: those in the grounding context (also as %) plus fixed pipeline facts. */
function allowedNumbers(contextJson: string): Set<string> {
  const set = new Set<string>();
  for (const m of contextJson.matchAll(/-?\d+(?:\.\d+)?(?:e-?\d+)?/gi)) {
    const n = Number(m[0]);
    addNumber(set, n);
    if (Math.abs(n) <= 1) addNumber(set, n * 100);
  }
  for (const n of [0, 1, 2, 3, 4, 8.7, 13.3, 18, 30, 31, 100, 512]) addNumber(set, n);
  return set;
}

/**
 * `reason` is the rejection category; `rule` is a structured rule identifier
 * (e.g. "affirmed:severity", "treatment#2"). Neither ever contains answer text.
 */
export type OutputVerdict = { ok: true } | { ok: false; reason: string; rule: string };

/** Verbatim machine labels in the context (safe to quote): classification label, etc. */
function contextLabels(contextJson: string): string[] {
  try {
    const ctx = JSON.parse(contextJson) as { classification?: { label?: unknown } | null };
    const label = ctx?.classification?.label;
    return typeof label === "string" ? [label] : [];
  } catch {
    return [];
  }
}

export function validateAnswer(answer: string, contextJson: string): OutputVerdict {
  const text = answer.trim();
  if (!text) return { ok: false, reason: "empty", rule: "empty" };
  if (text.length > 2500) return { ok: false, reason: "too_long", rule: "too_long" };
  const a = norm(text);
  const leak = OUT_LEAK.findIndex((r) => r.test(text));
  if (leak >= 0) return { ok: false, reason: "leak", rule: `leak#${leak + 1}` };
  const treatment = OUT_TREATMENT.findIndex((r) => r.test(a));
  if (treatment >= 0) return { ok: false, reason: "treatment", rule: `treatment#${treatment + 1}` };
  const claim = detectClinicalClaim(text, contextLabels(contextJson));
  if (claim) return { ok: false, reason: claim.category, rule: claim.rule };
  // Invented values/thresholds: every decimal, percentage or number-with-unit must be grounded.
  const allowed = allowedNumbers(contextJson);
  for (const m of text.matchAll(/(?<![\w.])(-?\d+(?:\.\d+)?)(\s*(?:g\/dl|mg\/dl|mg\/l|mmol\/l|%))?/gi)) {
    if (!m[1].includes(".") && !m[2]) continue;
    if (!allowed.has(String(Number(m[1])))) return { ok: false, reason: "ungrounded_number", rule: "ungrounded_number" };
  }
  return { ok: true };
}

/** Strip control/bidi characters and anything that could close the prompt's data envelopes. */
export function sanitizeUntrusted(text: string, maxChars: number): string {
  return text
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, "")
    .replace(/<\s*\/?\s*(report_context|conversation|question|system|assistant|user)\b[^>]*>/gi, "[removed]")
    .slice(0, maxChars)
    .trim();
}
