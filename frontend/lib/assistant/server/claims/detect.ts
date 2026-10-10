/**
 * SERVER-ONLY clause-level clinical-claim detector for model output.
 *
 * Every clinical term (whole token) found in a clause is judged:
 *  1. hedged negation in the sentence ("not only", "may not", ...)  -> REJECT
 *  2. double negation before the term                               -> REJECT
 *  3. object of a capability disclaimer ("cannot diagnose anemia")  -> allow
 *  4. no valid negation scope (= affirmed claim)                    -> REJECT
 *  5. negated "positive" term alone ("not normal")                  -> REJECT
 *  6. negated, but the subject is the user / a result / unknown     -> REJECT
 *  7. negated, subject is an artificial band/category/label          -> allow
 * Sentence-level rules reject denials ("no evidence of anemia"), invented
 * reference ranges, comparisons next to a negated term ("not mild, unlike C"),
 * and elliptical continuations ("Band A is not mild, but Band C is").
 */

import "server-only";

import {
  AMBIGUOUS_RE, COMPARATIVE_RE, DENIAL_RE, ELLIPTIC_END_RE, ELLIPTIC_START_RE,
  PERSON_CONDITION_RE, REFERENCE_RANGE_RE,
} from "@/lib/assistant/server/claims/patterns";
import { maskLabels, normalizeForClaims, splitClauses, tokenize } from "@/lib/assistant/server/claims/text";
import {
  CONDITION_PREFIX, DISCLAIMER_FILLER, DISCLAIMER_LEAD, DISCLAIMER_VERBS, DISEASE_RE, FILLER, INTERP, NEGATORS,
  NEUTRAL_NEXT, PERSON_TOKENS, POSITIVE, SEVERITY_ALWAYS, SEVERITY_TOPIC, STRONG_NEGATORS, VERB_LEADS, VERBS,
} from "@/lib/assistant/server/claims/vocab";

export type ClaimCategory = "diagnosis" | "clinical_severity";
export interface ClaimFinding {
  category: ClaimCategory;
  rule: string;
}

type Kind = "disease" | "severity" | "topic" | "interp";
type Topic = "band" | "result" | "person" | "neutral" | "unknown";

const words = (s: string) => new Set(s.split(/\s+/));
const SUBJ_BAND = words("band bands category categories class classes label labels zzlabelzz");
const SUBJ_RESULT = words(
  "result results value values level levels reading readings estimate estimates measurement measurements number " +
  "hemoglobin haemoglobin glucose albumin hb");
const SUBJ_NEUTRAL = words(
  "image images photo photos picture pictures photograph card strip strips roi region area lighting light quality " +
  "blur pipeline model models svr svm opencv feature features camera detection method confidence brightness " +
  "contrast question");
const PRONOUNS = words("it its they them these this those which that each both");
const EXTRA_NEUTRAL_NEXT = words("uncertainty accuracy error errors variance precision question questions idea news");
const EXTRA_DISCLAIMER_LEAD = words("a tool test device way method or be able to unable can will does do is are it this");

function rawKind(t: string | undefined): Kind | null {
  if (!t || t === ",") return null;
  if (DISEASE_RE.test(t)) return "disease";
  if (SEVERITY_ALWAYS.has(t)) return "severity";
  if (SEVERITY_TOPIC.has(t)) return "topic";
  if (INTERP.has(t)) return "interp";
  return null;
}

/** Clinical term at position i, or null when context makes it non-clinical ("low light", "lighting conditions"). */
function termKind(tk: string[], i: number): Kind | null {
  const kind = rawKind(tk[i]);
  if (!kind) return null;
  const next = tk[i + 1];
  if (next && (NEUTRAL_NEXT.has(next) || EXTRA_NEUTRAL_NEXT.has(next))) return null;
  if (/^conditions?$/.test(tk[i]) && CONDITION_PREFIX.has(tk[i - 1] ?? "")) return null;
  return kind;
}

/** Index of the negator whose scope covers tk[i], or -1. Any unexpected word breaks the scope. */
function negationIndex(tk: string[], i: number): number {
  for (let j = i - 1; j >= Math.max(0, i - 11); j--) {
    const w = tk[j];
    if (NEGATORS.has(w)) return j;
    if (w === ",") {
      const after = tk[j + 1] === "and" || tk[j + 1] === "or" ? tk[j + 2] : tk[j + 1];
      if (rawKind(tk[j - 1]) && rawKind(after)) continue;
      return -1;
    }
    if (w === "and") {
      if (tk[j - 1] === "," && rawKind(tk[j - 2]) && rawKind(tk[j + 1])) continue;
      return -1;
    }
    if (rawKind(w)) continue;
    if (FILLER.has(w)) continue;
    if (VERBS.has(w)) {
      const p = tk[j - 1] ?? "";
      if (NEGATORS.has(p) || VERB_LEADS.has(p)) continue;
      return -1;
    }
    return -1;
  }
  return -1;
}

/** "can not diagnose / tell whether you have / is not designed to detect ... <term>". */
function isDisclaimerObject(tk: string[], i: number): boolean {
  let j = i - 1;
  while (j >= 0 && i - j <= 9 && (DISCLAIMER_FILLER.has(tk[j]) || rawKind(tk[j]) || tk[j] === ",")) j--;
  // Only true capability verbs ("diagnose", "tell", "rule out"); "indicate"/"mean" are claims, not capabilities.
  if (j < 0 || !DISCLAIMER_VERBS.has(tk[j])) return false;
  let k = j - 1;
  while (k >= 0 && j - k <= 6 && (DISCLAIMER_LEAD.has(tk[k]) || EXTRA_DISCLAIMER_LEAD.has(tk[k]) ||
    DISCLAIMER_VERBS.has(tk[k]) || tk[k] === ",")) {
    if (tk[k] === "unable") return true;
    k--;
  }
  return k >= 0 && (tk[k] === "not" || tk[k] === "never");
}

function nounTopic(w: string): Topic | null {
  if (SUBJ_BAND.has(w)) return "band";
  if (PERSON_TOKENS.has(w)) return "person";
  if (SUBJ_RESULT.has(w)) return "result";
  if (SUBJ_NEUTRAL.has(w)) return "neutral";
  return null;
}

const SUBJECT_END = words("is are was were be does do did can will may might could would should has have means mean indicates indicate represents represent suggests suggest shows show corresponds correspond carry carries");

/**
 * Grammatical subject of the clause: the last topical noun BEFORE the first verb
 * (and before position `limit`). Object nouns ("... is not a severity level")
 * are ignored. Null => pronoun / elided subject, so the caller inherits.
 */
function subjectTopic(tk: string[], limit: number): Topic | null {
  let end = Math.min(limit, tk.length);
  for (let k = 0; k < end; k++) if (SUBJECT_END.has(tk[k]) || VERBS.has(tk[k])) { end = k; break; }
  for (let k = end - 1; k >= 0; k--) {
    const t = nounTopic(tk[k]);
    if (t) return t;
  }
  return null;
}

const category = (kind: Kind): ClaimCategory => (kind === "disease" ? "diagnosis" : "clinical_severity");

/** Judge one clause. Returns a finding, or null when every clinical term in it is acceptable. */
function judgeClause(clause: string, inherited: Topic, sentence: string): { finding: ClaimFinding | null; topic: Topic } {
  const tk = tokenize(clause);
  const first = tk[0] ?? "";
  // Topic of this clause: its own nearest noun subject, else inherited (pronoun / elided subject).
  let clauseTopic: Topic = inherited;
  const own = subjectTopic(tk, tk.length);
  if (own && !(PRONOUNS.has(first) && own === "neutral")) clauseTopic = own;
  const mentionsPerson = tk.some((w) => PERSON_TOKENS.has(w));
  const anyResultWord = tk.some((w) => SUBJ_RESULT.has(w));

  for (let i = 0; i < tk.length; i++) {
    const kind = termKind(tk, i);
    if (!kind) continue;
    const subj = subjectTopic(tk, i) ?? clauseTopic;
    // Topic-dependent words ("normal", "low", ...) only count when the clause is about a result/band/person.
    if ((kind === "topic" || kind === "interp") && !(subj === "band" || subj === "result" || subj === "person" ||
      mentionsPerson || anyResultWord || clauseTopic === "band" || clauseTopic === "result")) continue;

    const rule = kind;
    if (AMBIGUOUS_RE.test(sentence)) return { finding: { category: category(kind), rule: `hedged_negation:${kind}` }, topic: clauseTopic };

    if (isDisclaimerObject(tk, i)) continue;

    const neg = negationIndex(tk, i);
    if (neg < 0) return { finding: { category: category(kind), rule: `affirmed:${rule}` }, topic: clauseTopic };
    // "no" negates nouns ("no anemia"), not adjectives: "no mild matter" means serious.
    if (tk[neg] === "no" && kind !== "disease") {
      return { finding: { category: category(kind), rule: `idiomatic_no:${kind}` }, topic: clauseTopic };
    }
    // Double negation before the negator ("not ... not mild", "never not severe").
    for (let k = Math.max(0, neg - 4); k < neg; k++) {
      if (STRONG_NEGATORS.has(tk[k])) return { finding: { category: category(kind), rule: `double_negation:${kind}` }, topic: clauseTopic };
    }
    // "not normal" asserts abnormal — only OK inside a list that also negates a non-positive term.
    if (POSITIVE.has(tk[i])) {
      const span = tk.slice(neg + 1, Math.min(tk.length, i + 6));
      const hasNegativeSibling = span.some((w, idx) => {
        const kk = rawKind(w);
        return kk && !POSITIVE.has(w) && negationIndex(tk, neg + 1 + idx) === neg;
      });
      if (!hasNegativeSibling) return { finding: { category: category(kind), rule: `negated_positive:${kind}` }, topic: clauseTopic };
    }
    // Negated statements are only accepted about the artificial bands, never about the user or a result.
    if (mentionsPerson || subj === "person") return { finding: { category: category(kind), rule: `person_claim:${kind}` }, topic: clauseTopic };
    if (subj !== "band") return { finding: { category: category(kind), rule: `negated_non_band:${kind}` }, topic: clauseTopic };
    if (COMPARATIVE_RE.test(sentence)) return { finding: { category: category(kind), rule: `comparative:${kind}` }, topic: clauseTopic };
  }
  return { finding: null, topic: clauseTopic };
}

function hasClinicalTerm(clause: string): boolean {
  const tk = tokenize(clause);
  return tk.some((_, i) => termKind(tk, i) !== null);
}

/**
 * Detect any clinical claim in a model answer. `labels` are verbatim machine labels
 * from the report (e.g. the classification label) that may be quoted safely.
 */
export function detectClinicalClaim(answer: string, labels: readonly string[] = []): ClaimFinding | null {
  const normalized = normalizeForClaims(maskLabels(answer, labels));
  let topic: Topic = "unknown";
  let prevNegatedClinical = false;

  // prevNegatedClinical carries across sentence boundaries so "Band A is not mild. Band C is." is caught.
  for (const clauses of splitClauses(normalized)) {
    const sentence = clauses.join(" , ");
    const sentenceTokens = tokenize(sentence);
    if (DENIAL_RE.test(sentence) && sentenceTokens.some((_, i) => termKind(sentenceTokens, i) === "disease")) {
      return { category: "diagnosis", rule: "denial_of_condition" };
    }
    if (PERSON_CONDITION_RE.test(sentence)) return { category: "diagnosis", rule: "person_condition_reference" };
    if (REFERENCE_RANGE_RE.test(sentence)) return { category: "clinical_severity", rule: "reference_range" };

    for (const clause of clauses) {
      const first = tokenize(clause)[0] ?? "";
      const inherited: Topic = PRONOUNS.has(first) || clause.split(" ").length <= 2 || /^(?:does|do|did|is|are|was|were|has|have|can|will|may|might|could|would|should|means?|indicates?|represents?)\b/.test(clause)
        ? topic : "unknown";
      // "Band A is not mild, but Band C is." / "So is Band C." — the elided predicate inherits the claim.
      if (prevNegatedClinical && (ELLIPTIC_END_RE.test(clause) || ELLIPTIC_START_RE.test(clause)) && !hasClinicalTerm(clause)) {
        return { category: "clinical_severity", rule: "elliptical_affirmation" };
      }
      const { finding, topic: t } = judgeClause(clause, inherited, sentence);
      if (finding) return finding;
      topic = t;
      prevNegatedClinical = hasClinicalTerm(clause);
    }
  }
  return null;
}
