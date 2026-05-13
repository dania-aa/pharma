import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Brain, MessageSquare, BarChart2, FlaskConical, Plus, Trash2 } from "lucide-react";

const navItems = [
  { to: "/", icon: MessageSquare, label: "Research Assistant" },
  { to: "/benchmark", icon: BarChart2, label: "Model Accuracy" },
  { to: "/predict", icon: FlaskConical, label: "Predict Trial" },
];

export default function Sidebar({ conversations = [], onNewChat, onDeleteConversation }) {
  return (
    <aside className="w-64 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <Brain size={18} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">TrialMind</p>
            <p className="text-xs text-slate-500">Clinical AI</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 py-4 border-b border-slate-800">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm mb-0.5 transition-colors ${
                isActive
                  ? "bg-brand-600/20 text-brand-400 font-medium"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        <div className="flex items-center justify-between mb-2 px-2">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
            Recent Chats
          </p>
          <button
            onClick={onNewChat}
            className="w-6 h-6 rounded-md bg-slate-800 hover:bg-slate-700 flex items-center
                       justify-center text-slate-400 hover:text-white transition-colors"
            title="New chat"
          >
            <Plus size={14} />
          </button>
        </div>
        <div className="space-y-0.5">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className="group flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-800
                         cursor-pointer transition-colors"
            >
              <MessageSquare size={13} className="text-slate-500 flex-shrink-0" />
              <span className="text-xs text-slate-400 truncate flex-1">
                {conv.title}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConversation?.(conv.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400
                           transition-all"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="text-xs text-slate-600 px-2 py-2">No conversations yet</p>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-800">
        <p className="text-xs text-slate-600">
          Powered by AWS Bedrock · LangGraph
        </p>
      </div>
    </aside>
  );
}
