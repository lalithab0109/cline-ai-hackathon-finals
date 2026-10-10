"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";

/**
 * Safe Markdown renderer for Aarogya AI ASSISTANT messages only (user messages
 * stay plain text).
 *
 * Security model (no raw HTML is ever rendered):
 *  - react-markdown builds React elements from a Markdown AST; it never uses
 *    dangerouslySetInnerHTML, and raw HTML in the source is ignored because
 *    no rehype-raw plugin is installed (`skipHtml` drops it entirely).
 *  - `allowedElements` is a strict allow-list: headings, paragraphs, lists,
 *    emphasis, inline/block code, blockquote, line breaks and rules. Links and
 *    images are NOT allowed; `unwrapDisallowed` keeps their visible text only,
 *    so a link becomes plain text and an image is reduced to its alt text.
 *    Nothing is fetched and nothing is clickable.
 *  - `urlTransform` returns "" as a second layer, in case an element with a
 *    URL ever slipped through.
 * Headings are rendered as small bold text so model output cannot dominate
 * the page or impersonate app UI.
 */

const ALLOWED = [
  "p", "br", "strong", "em", "del", "ul", "ol", "li", "code", "pre", "blockquote", "hr",
  "h1", "h2", "h3", "h4", "h5", "h6",
];

const heading = ({ children }: { children?: React.ReactNode }) => (
  <p className="mt-2.5 text-sm font-semibold text-slate-900 first:mt-0">{children}</p>
);

const components: Components = {
  p: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-5 first:mt-0">{children}</ul>,
  ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1 pl-5 first:mt-0">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  code: ({ children }) => (
    <code className="break-words rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[0.8125rem] text-slate-800">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-100 p-2.5 text-xs [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-slate-600">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-slate-200" />,
  h1: heading,
  h2: heading,
  h3: heading,
  h4: heading,
  h5: heading,
  h6: heading,
};

export default function AssistantMarkdown({ content }: { content: string }) {
  return (
    <div className="break-words text-sm leading-relaxed text-slate-700" data-testid="assistant-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkBreaks]}
        allowedElements={ALLOWED}
        unwrapDisallowed
        skipHtml
        urlTransform={() => ""}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
