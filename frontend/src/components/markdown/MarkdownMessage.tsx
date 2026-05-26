import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "./MarkdownMessage.css";

type CopyBtnProps = {
  text: string;
};

function CopyBtn({ text }: CopyBtnProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="markdown-message__copy-btn"
      aria-label="Copy code"
      title="Copy"
      type="button"
    >
      複製
    </button>
  );
}

type MarkdownMessageProps = {
  text: string;
};

const components: Components = {
  h1: ({ node, ...props }) => (
    <h1 className="markdown-message__h1" {...props} />
  ),
  h2: ({ node, ...props }) => (
    <h2 className="markdown-message__h2" {...props} />
  ),
  p: ({ node, ...props }) => (
    <p className="markdown-message__p" {...props} />
  ),
  a: ({ node, ...props }) => (
    <a
      target="_blank"
      rel="noreferrer"
      className="markdown-message__link"
      {...props}
    />
  ),
  ul: ({ node, ...props }) => (
    <ul className="markdown-message__ul" {...props} />
  ),
  ol: ({ node, ...props }) => (
    <ol className="markdown-message__ol" {...props} />
  ),
  table: ({ node, ...props }) => (
    <div className="markdown-message__table-wrap">
      <table className="markdown-message__table" {...props} />
    </div>
  ),
  th: ({ node, ...props }) => (
    <th className="markdown-message__th" {...props} />
  ),
  td: ({ node, ...props }) => (
    <td className="markdown-message__td" {...props} />
  ),
  img: ({ src, alt }) => (
    <img
      src={src}
      alt={alt ?? ""}
      style={{ maxWidth: "100%", borderRadius: 8, margin: "8px 0", display: "block" }}
    />
  ),
  code: ({ className, children, ...props }) => {
    const match = /language-(\w+)/.exec(className || "");
    const raw = String(children ?? "");
    const isBlock = Boolean(match);

    if (!isBlock) {
      return (
        <code className="markdown-message__inline-code" {...props}>
          {raw}
        </code>
      );
    }

    return (
      <div className="markdown-message__code-block">
        <CopyBtn text={raw} />
        <SyntaxHighlighter
          language={match?.[1] || "plaintext"}
          style={oneDark}
          PreTag="div"
          customStyle={{
            margin: "8px 0",
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          {raw.replace(/\n$/, "")}
        </SyntaxHighlighter>
      </div>
    );
  },
};

function urlTransform(url: string): string {
  if (url.startsWith("data:")) return url;
  // default safe protocols
  if (/^https?:\/\//.test(url) || url.startsWith("mailto:")) return url;
  return url;
}

export function MarkdownMessage({ text }: MarkdownMessageProps) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={urlTransform}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}