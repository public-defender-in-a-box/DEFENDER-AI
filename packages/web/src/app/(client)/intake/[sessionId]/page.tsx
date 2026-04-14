"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import type { IntakeMessage } from "@/types/agents";
import { ChatInterface } from "@/components/intake/ChatInterface";
import { IntakeProgress } from "@/components/intake/IntakeProgress";
import { useVoiceMode } from "@/hooks/use-voice-mode";

interface ProgressState {
  phaseName: string;
  phaseIndex: number;
  totalPhases: number;
  completionPercentage: number;
}

function useIntakeWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<IntakeMessage[]>([]);
  const [progress, setProgress] = useState<ProgressState>({
    phaseName: "",
    phaseIndex: 0,
    totalPhases: 5,
    completionPercentage: 0,
  });
  const [connected, setConnected] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(
      `ws://localhost:8000/api/v1/ws/intake/${encodeURIComponent(sessionId)}`
    );
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError("");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "progress") {
        setProgress({
          phaseName: data.phaseName || "",
          phaseIndex: data.phaseIndex ?? 0,
          totalPhases: data.totalPhases ?? 5,
          completionPercentage: data.completionPercentage ?? 0,
        });
        return;
      }

      if (data.type === "error") {
        setError(data.content);
        return;
      }

      if (data.type === "complete") {
        setComplete(true);
      }

      // All message types (system, message, complete) get added to the chat
      const msg: IntakeMessage = {
        id: data.messageId || crypto.randomUUID(),
        timestamp: data.timestamp || new Date().toISOString(),
        sender: "SYSTEM",
        content: data.content,
      };
      setMessages((prev) => [...prev, msg]);
    };

    ws.onclose = (event) => {
      setConnected(false);
      // Only show error if it wasn't a clean close
      if (event.code !== 1000 && event.code !== 1005) {
        setError("Connection lost. Please refresh the page.");
      }
    };

    // onerror always fires before onclose — let onclose handle the message
    ws.onerror = () => {};

    return () => {
      ws.close();
    };
  }, [sessionId]);

  const send = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      wsRef.current.send(text);

      // Add client message to local state
      const clientMsg: IntakeMessage = {
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        sender: "CLIENT",
        content: text,
      };
      setMessages((prev) => [...prev, clientMsg]);
    },
    []
  );

  return { messages, progress, connected, complete, error, send };
}

export default function IntakeSessionPage({
  params,
}: {
  params: { sessionId: string };
}) {
  const { messages, progress, connected, complete, error, send } =
    useIntakeWebSocket(params.sessionId);

  const voice = useVoiceMode({
    onTranscript: send,
    autoSend: true,
  });

  // Track last spoken message to avoid re-speaking
  const lastSpokenIdRef = useRef<string | null>(null);

  // TTS trigger: speak latest SYSTEM message when voice is enabled
  useEffect(() => {
    if (!voice.voiceEnabled || messages.length === 0) return;

    const lastMsg = messages[messages.length - 1];
    if (
      lastMsg.sender === "SYSTEM" &&
      lastMsg.id !== lastSpokenIdRef.current
    ) {
      lastSpokenIdRef.current = lastMsg.id;
      voice.speakText(lastMsg.content);
    }
  }, [messages, voice.voiceEnabled, voice.speakText]);

  // Auto-listen after AI finishes speaking
  const wasSpeakingRef = useRef(false);
  useEffect(() => {
    if (voice.isSpeaking) {
      wasSpeakingRef.current = true;
      return;
    }

    if (wasSpeakingRef.current && voice.voiceEnabled && !complete) {
      wasSpeakingRef.current = false;
      const timer = setTimeout(() => {
        if (voice.voiceEnabled && !voice.isListening && !voice.isSpeaking) {
          voice.startListening();
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [voice.isSpeaking, voice.voiceEnabled, voice.isListening, voice.startListening, complete]);

  return (
    <div>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "0.25rem",
      }}>
        <h1 style={{ fontSize: "1.25rem", margin: 0 }}>Intake Interview</h1>

        {voice.browserSupported && (
          <button
            onClick={voice.toggleVoice}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "0.35rem 0.75rem",
              borderRadius: 6,
              border: `1px solid ${voice.voiceEnabled ? "#3b82f6" : "#d1d5db"}`,
              background: voice.voiceEnabled ? "#eff6ff" : "#fff",
              color: voice.voiceEnabled ? "#3b82f6" : "#6b7280",
              cursor: "pointer",
              fontSize: "0.8rem",
              fontWeight: 500,
            }}
          >
            {voice.voiceEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
            {voice.voiceEnabled ? "Voice On" : "Voice Off"}
          </button>
        )}
      </div>

      <p style={{ fontSize: "0.8rem", color: "#6b7280", marginBottom: "1rem" }}>
        Session: {params.sessionId} — Protected by attorney-client privilege
      </p>

      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            padding: "0.5rem 0.75rem",
            marginBottom: "0.75rem",
            color: "#dc2626",
            fontSize: "0.85rem",
          }}
        >
          {error}
        </div>
      )}

      {voice.error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            padding: "0.5rem 0.75rem",
            marginBottom: "0.75rem",
            color: "#dc2626",
            fontSize: "0.85rem",
          }}
        >
          {voice.error}
        </div>
      )}

      {voice.voiceEnabled && (
        <div
          style={{
            fontSize: "0.8rem",
            color: voice.isSpeaking ? "#7c3aed" : voice.isListening ? "#16a34a" : "#9ca3af",
            marginBottom: "0.5rem",
            fontWeight: 500,
          }}
        >
          {voice.isSpeaking
            ? "Speaking..."
            : voice.isListening
              ? "Listening..."
              : "Voice ready"}
        </div>
      )}

      <IntakeProgress
        completionPercentage={progress.completionPercentage}
        questionsAnswered={progress.phaseIndex}
        totalQuestions={progress.totalPhases}
        phaseName={progress.phaseName}
      />

      <ChatInterface
        messages={messages}
        onSend={send}
        disabled={complete || !connected}
        voiceMode={voice.voiceEnabled}
        isListening={voice.isListening}
        isSpeaking={voice.isSpeaking}
        onMicStart={voice.startListening}
        onMicStop={voice.stopListening}
        transcript={voice.transcript}
      />

      {complete && (
        <div
          style={{
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: 6,
            padding: "0.75rem",
            marginTop: "0.75rem",
            fontSize: "0.85rem",
            color: "#166534",
          }}
        >
          Interview complete. Your attorney will review this information and be in touch.
        </div>
      )}

      {!connected && !complete && !error && (
        <p style={{ color: "#9ca3af", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          Connecting...
        </p>
      )}
    </div>
  );
}
