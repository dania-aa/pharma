import React from "react";
import ReactMarkdown from "react-markdown";
import { Brain, User, Wrench } from "lucide-react";
import ChartRenderer from "./ChartRenderer";

function ToolCallBadge({ calls }) {
  if (!calls?.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2 mb-3">
      {calls.map((tc, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                     bg-slate-800 text-slate-400 border border-slate-700"
        >
          <Wrench size={10} />
          {tc.tool}
        </span>
      ))}
    </div>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 mb-4">
        <div className="max-w-[75%] bg-brand-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
          {message.content}
        </div>
        <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0 mt-0.5">
          <User size={16} className="text-slate-300" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Brain size={16} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <ToolCallBadge calls={message.tool_calls} />
        <div className="prose-dark text-sm text-slate-200">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
        {message.charts?.map((chart, i) => (
          <ChartRenderer key={i} chartData={chart} />
        ))}
      </div>
    </div>
  );
}
