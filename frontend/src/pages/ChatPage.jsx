import React, { useEffect, useRef, useState } from "react";
import { Send, Loader2, Brain, Zap } from "lucide-react";
import MessageBubble from "../components/MessageBubble";
import { useChat } from "../hooks/useChat";
import { getSuggestedQueries } from "../api/client";

const WELCOME_SUGGESTIONS = [
  "What is the overall success rate of Phase 3 trials?",
  "Show a chart of success rates by therapeutic area",
  "Compare industry vs NIH-sponsored trials",
  "Predict success for a Phase 3 oncology drug with 500 patients",
  "How does enrollment size affect trial success?",
  "Show trial volume over time as a chart",
];

export default function ChatPage() {
  const { messages, isLoading, error, send, reset } = useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    send(input.trim());
    setInput("");
  };

  const handleSuggestion = (text) => {
    send(text);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="px-6 py-4 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold text-white">Research Assistant</h1>
          <p className="text-xs text-slate-500">Ask anything about clinical trial data</p>
        </div>
        {!isEmpty && (
          <button onClick={reset} className="btn-ghost text-xs">
            New chat
          </button>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isEmpty ? (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-10 mt-8">
              <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-4">
                <Brain size={28} className="text-white" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">
                Welcome to TrialMind
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                I can analyse hundreds of thousands of real clinical trials. Ask me about
                success rates, compare sponsors, generate charts, or predict whether a new
                trial design is likely to succeed.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {WELCOME_SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSuggestion(s)}
                  className="text-left p-3.5 rounded-xl bg-slate-900 border border-slate-800
                             hover:border-brand-500/50 hover:bg-slate-800 transition-all group"
                >
                  <div className="flex items-start gap-2.5">
                    <Zap size={14} className="text-brand-400 mt-0.5 flex-shrink-0 group-hover:text-brand-300" />
                    <span className="text-sm text-slate-300 group-hover:text-white leading-snug">
                      {s}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div className="flex gap-3 mb-4">
                <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center flex-shrink-0">
                  <Brain size={16} className="text-white" />
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-400 py-2">
                  <Loader2 size={16} className="animate-spin text-brand-400" />
                  Analysing...
                </div>
              </div>
            )}
            {error && (
              <div className="bg-red-900/20 border border-red-800 text-red-300 text-sm rounded-xl px-4 py-3 mb-4">
                {error}
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-800 flex-shrink-0">
        <form
          onSubmit={handleSubmit}
          className="max-w-3xl mx-auto flex items-end gap-2"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            rows={1}
            placeholder="Ask about clinical trials…"
            className="flex-1 input resize-none leading-relaxed py-3 max-h-36"
            style={{ height: "auto" }}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="btn-primary h-11 w-11 flex items-center justify-center flex-shrink-0 p-0"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </form>
        <p className="text-center text-xs text-slate-700 mt-2">
          TrialMind uses real data from ClinicalTrials.gov · AI predictions are for research only
        </p>
      </div>
    </div>
  );
}
