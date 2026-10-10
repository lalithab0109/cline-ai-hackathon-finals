/**
 * SERVER-ONLY vocabulary for the clause-level clinical-claim detector
 * (see ./detect.ts). Every entry is matched as a WHOLE TOKEN, never as a
 * substring, so "low" does not match "lowest" or "lower".
 */

import "server-only";

const words = (s: string) => new Set(s.split(/\s+/).filter(Boolean));

/** Disease / condition terms (stems allowed: anemia, anaemic, diabetes, deficiency, ...). */
export const DISEASE_RE =
  /^(?:(?:anemi|anaemi|diabet|prediabet|hypergly|hypogly|thalass|deficien|albuminuri|proteinuri|nephropath)[a-z]*|ckd|diseases?|disorders?|illness(?:es)?|infections?|cancers?|conditions?|sickness|sick|ill)$/;

/** Clinical whatever the topic. */
export const SEVERITY_ALWAYS = words(
  "mild mildly moderate moderately severe severely abnormal abnormality abnormalities dangerous critical " +
  "pathological risk risky threatening");

/** Clinical only when the sentence is about a result, a band or the user. */
export const SEVERITY_TOPIC = words("normal healthy unhealthy");
export const INTERP = words(
  "low high elevated reduced decreased increased concerning worrying alarming reassuring fine okay ok good bad " +
  "serious significant insufficient adequate sufficient acceptable worse better poor optimal");

/** Negating these asserts the opposite ("not normal" means abnormal), so negation alone never clears them. */
export const POSITIVE = words("normal healthy fine okay ok good adequate sufficient acceptable reassuring optimal better");

/** A following token that makes the term about the photo / range layout ("low light", "anemia-style screening"). */
export const NEUTRAL_NEXT = words(
  "quality resolution light lighting lit photo photos photograph image images picture pictures blur blurriness " +
  "contrast confidence brightness exposure sharpness noise focus angle framing camera score scores room daylight " +
  "end third half portion part capture glare shadow shadows saturation detail style screening research");

/** A preceding token that makes "conditions" mean photo conditions ("lighting conditions"). */
export const CONDITION_PREFIX = words(
  "lighting light photo capture imaging shooting room viewing testing environmental camera good better poor even " +
  "bright dim different these those similar ideal proper suitable controlled same");

export const NEGATORS = words("not no never neither nor without");
export const STRONG_NEGATORS = words("not no never without");

/** Predicate verbs: allowed inside a negation scope only right after the negator or after "or"/"nor"/"to". */
export const VERBS = words(
  "is are was were be means mean meant indicates indicate indicated represents represent suggests suggest shows " +
  "show signals signal reflects reflect implies imply corresponds correspond points point equals equal denotes " +
  "denote classifies classify reveals reveal has have had confirms confirm signifies signify describe describes " +
  "measure measures identify identifies define defines correlate correlates relate relates map maps refer refers " +
  "carry carries");
export const VERB_LEADS = words("or nor to");

/** Neutral words allowed anywhere inside a negation scope. Anything else breaks the scope. */
export const FILLER = words(
  "a an the any of or nor to as for with in on by from such like kind type sort form forms level levels degree " +
  "degrees grade grades stage stages category categories class classes label labels band bands marker markers " +
  "sign signs indicator indicators evidence diagnosis diagnoses assessment severity status state medical clinical " +
  "health real world actual true official standard meaning relation relationship connection link bearing " +
  "association associated linked related tied connected correlated equivalent mapped been being read interpreted " +
  "considered seen taken understood viewed used intended designed zzlabelzz hemoglobin haemoglobin glucose albumin " +
  "hb scale rating ranking diagnostic artificial demonstration synthetic other kidney renal iron blood liver heart");

/** "cannot <verb> ... <term>" capability disclaimers. */
export const DISCLAIMER_VERBS = words(
  "diagnose diagnosing determine detect identify assess tell say confirm establish rule replace decide predict " +
  "evaluate interpret prove");
export const DISCLAIMER_FILLER = words(
  "whether if you your someone anyone a an the any person has have is are or out it for of presence absence " +
  "conditions condition like such as other kidney renal iron blood value values result results level levels reading " +
  "readings this that hemoglobin haemoglobin glucose albumin estimate");
export const DISCLAIMER_LEAD = words("to be able designed meant intended used and");
export const PERSON_TOKENS = words("you your yours yourself patient patients person someone user users people");

export const PERSON_RE = /\b(?:you|your|yours|yourself|patient|patients|person|someone|user|users|people)\b/;
export const RESULT_RE =
  /\b(?:result|results|value|values|level|levels|reading|readings|estimate|estimates|measurement|measurements|number|count|hemoglobin|haemoglobin|glucose|albumin|hb)\b/;
/** Topic = the artificial bands / categories / machine labels. */
export const BAND_RE = /\b(?:band|bands|category|categories|class|classes|label|labels|zzlabelzz)\b/;
/** Clause openers that continue the previous clause's subject ("it", "they", or elided: "does not ..."). */
export const INHERIT_START = words(
  "it its they these this those each both neither none which that does do did is are was were can may might " +
  "could would will has have means mean indicates represents should");
