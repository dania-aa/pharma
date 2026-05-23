import { useState, useCallback, useRef } from "react";
import { sendMessage } from "../api/client";

export function useChat(initialConversationId = null) {
  const [conversationId, setConversationId] = useState(initialConversationId);
  const [messages, setMessages] = useState([]);
  const [charts, setCharts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const send = useCallback(
    async (text) => {
      if (!text.trim() || isLoading) return;

      const userMsg = { role: "user", content: text, id: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const result = await sendMessage(conversationId, text);
        setConversationId(result.conversation_id);
        const assistantMsg = {
          ...result.message,
          id: Date.now() + 1,
          charts: result.charts || [],
          tool_calls: result.tool_calls || [],
        };
        setMessages((prev) => [...prev, assistantMsg]);
        if (result.charts?.length) {
          setCharts((prev) => [...prev, ...result.charts]);
        }
      } catch (err) {
        setError(err.response?.data?.error || err.message || "Something went wrong");
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, isLoading]
  );

  const reset = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setCharts([]);
    setError(null);
  }, []);

  return { conversationId, messages, charts, isLoading, error, send, reset };
}
