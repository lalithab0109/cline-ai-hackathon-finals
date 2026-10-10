/**
 * SERVER-ONLY text preparation for the clinical-claim detector:
 * label masking, normalisation, sentence/clause splitting, tokenisation.
 */

import "server-only";

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Replace verbatim machine labels from the report (e.g. "artificial_band_A_4.0-8.7",
 * "moderate_abnormality") with a neutral placeholder so quoting the label is not
 * read as a claim. Prose versions are only masked when quoted.
 */
export function maskLabels(text: string, labels: readonly string[]): string {
  let out = text.replace(/artificial_band_[abc](?:_[\d.]+[-\u2013][\d.]+)?/gi, " zzlabelzz ");
  for (const label of labels) {
    if (!label || !label.includes("_")) continue;
    out = out.replace(new RegExp(escapeRe(label), "gi"), " zzlabelzz ");
    const prose = escapeRe(label.replace(/_/g, " "));
    out = out.replace(new RegExp(`["'\u201C\u201D\u2018\u2019\`]\\s*${prose}\\s*["'\u201C\u201D\u2018\u2019\`]`, "gi"), " zzlabelzz ");
  }
  return out;
}

export function normalizeForClaims(text: string): string {
  return text
    .normalize("NFKC")
    .replace(/[\u00AD\u200B-\u200F\u2060-\u2064\uFEFF]/g, "")
    .toLowerCase()
    .replace(/[\u2018\u2019`\u00B4]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\bcan'?t\b|\bcannot\b/g, "can not")
    .replace(/\bwon'?t\b/g, "will not")
    .replace(/n't\b/g, " not")
    .replace(/\b(?:rather than|instead of|as opposed to)\b/g, " not ")
    .replace(/[*#>~_|]+/g, " ")
    .replace(/["']/g, " ")
    .replace(/[ \t]+/g, " ");
}

const SUBJ = "(?:it|this|that|they|these|those|which|band [abc]|the band|the category|you|your \\w+)";
const VERB =
  "(?:is|are|was|were|means?|indicates?|represents?|suggests?|shows?|signals?|reflects?|implies|corresponds?|" +
  "points?|has|have|may|might|could|would|will|does|do|did|can|likely|probably)\\b";
const CONTRAST =
  "but|however|although|though|whereas|yet|while|nevertheless|nonetheless|except|instead|rather|actually|" +
  "in fact|that said|just kidding|on the other hand";

const SENTENCE_SPLIT = /(?<!\d)[.!?]+|[.!?]+(?!\d)|[;\n\u2022]+|\s[\u2013\u2014-]+\s|(?<=\D)[\u2013\u2014]|[\u2013\u2014](?=\D)/;
const CLAUSE_SPLIT = new RegExp(
  `[:()\\[\\]{}]|\\s*,?\\s*\\b(?:${CONTRAST})\\b` +
  `|,\\s*(?=${SUBJ}\\s+${VERB})` +
  `|\\s(?:and|so|thus|therefore|hence|plus)\\s+(?=(?:${SUBJ}\\s+)?${VERB})`);

/** Sentences (outer) of clauses (inner), in reading order. */
export function splitClauses(normalized: string): string[][] {
  return normalized
    .split(SENTENCE_SPLIT)
    .map((s) => (s ?? "").split(CLAUSE_SPLIT).map((c) => (c ?? "").replace(/^[\s,]+|[\s,]+$/g, "")).filter(Boolean))
    .filter((clauses) => clauses.length > 0);
}

/** Whole-word tokens; commas are kept as tokens for list handling; hyphens split words. */
export function tokenize(clause: string): string[] {
  return clause.match(/[a-z0-9]+|,/g) ?? [];
}
