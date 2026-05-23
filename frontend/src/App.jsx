import React, { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatPage from "./pages/ChatPage";
import BenchmarkPage from "./pages/BenchmarkPage";
import PredictPage from "./pages/PredictPage";
import { listConversations, deleteConversation } from "./api/client";

export default function App() {
  const [conversations, setConversations] = useState([]);

  const loadConversations = () => {
    listConversations()
      .then(setConversations)
      .catch(() => {});
  };

  useEffect(() => {
    loadConversations();
    const interval = setInterval(loadConversations, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = async (id) => {
    await deleteConversation(id).catch(() => {});
    setConversations((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        onNewChat={loadConversations}
        onDeleteConversation={handleDelete}
      />
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
          <Route path="/predict" element={<PredictPage />} />
        </Routes>
      </main>
    </div>
  );
}
