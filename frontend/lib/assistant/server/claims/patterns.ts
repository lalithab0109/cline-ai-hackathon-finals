/**
 * SERVER-ONLY sentence-level patterns for the clinical-claim detector.
 * Each pattern runs on ONE normalised sentence or clause, never the whole answer.
 */

import "server-only";

/** Hedged / inverted / quantified negation: never trusted next to a clinical term. */
export const AMBIGUOUS_RE = new RegExp(
  "\\bnot (?:only|just|merely|simply|necessarily|exactly|entirely|completely|always|clear(?:ly)?|certain(?:ly)?|" +
  "sure|impossible|unlikely|yet|be ruled out|ruled out|be excluded|excluded|true|correct|accurate|right|wrong|" +
  "false|untrue|incorrect|the case|all|every)\\b|\\b(?:may|might|could|would|probably|possibly|likely|perhaps|" +
  "maybe)\\s+(?:\\w+\\s+)?not\\b|\\b(?:unlikely|hardly|barely|rarely|seldom|almost|technically|arguably)\\b");

/** Comparisons can turn a negation into an implied claim about another band ("not mild, unlike Band C"). */
export const COMPARATIVE_RE = /\b(?:unlike|than|contrast|compared|versus|vs|whereas|opposite|unless|except|otherwise)\b/;

/** "no evidence of anemia" — denying a condition is still a clinical conclusion. */
export const DENIAL_RE =
  /\b(?:no|not any|without|absence of|lack of|free of|free from)\s+(?:\w+\s+){0,2}?(?:signs?|evidence|indications?|traces?|symptoms?|risk)\s+(?:of|for)\b/;

/** "you have it", "you are one" — condition by reference. */
export const PERSON_CONDITION_RE =
  /\byou (?:\w+ )?(?:have|has|got|suffer from|are suffering from|are|re) (?:it|this|that|them|one)\b/;

/** Invented clinical reference ranges. */
export const REFERENCE_RANGE_RE =
  /\b(?:normal|healthy|reference|typical|expected|target|safe|standard) (?:range|ranges|interval|intervals|values?|levels?|limits?|thresholds?|cut ?offs?)\b/;

/** Elliptical continuation that inherits a claim: "... but Band C is.", "So is Band C". */
export const ELLIPTIC_END_RE =
  /\b(?:is|are|was|were|does|do|did|can|will|might|could|would|has|have|may)(?: not)?(?: too| also| though| either| as well| instead)?$/;
export const ELLIPTIC_START_RE = /^(?:and )?(?:so|same|likewise|similarly) (?:is|are|does|do|was|were|for|with|goes)\b/;
