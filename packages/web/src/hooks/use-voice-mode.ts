"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseVoiceModeOptions {
  onTranscript: (text: string) => void;
  autoSend?: boolean;
}

interface UseVoiceModeReturn {
  // State
  voiceEnabled: boolean;
  browserSupported: boolean;
  isListening: boolean;
  isSpeaking: boolean;
  transcript: string;
  micPermission: "prompt" | "granted" | "denied";
  error: string | null;
  // Actions
  toggleVoice: () => void;
  startListening: () => void;
  stopListening: () => void;
  speakText: (text: string) => Promise<void>;
  stopSpeaking: () => void;
}

export function useVoiceMode({
  onTranscript,
  autoSend = true,
}: UseVoiceModeOptions): UseVoiceModeReturn {
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [micPermission, setMicPermission] = useState<"prompt" | "granted" | "denied">("prompt");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  // Check browser support
  const browserSupported =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      audioRef.current?.pause();
      abortRef.current?.abort();
    };
  }, []);

  // --- STT ---

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    if (!browserSupported) return;

    // Stop any ongoing TTS to prevent echo
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsSpeaking(false);
    }
    abortRef.current?.abort();

    setError(null);
    setTranscript("");

    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setIsListening(true);
      setMicPermission("granted");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      if (final) {
        setTranscript(final);
        if (autoSend) {
          onTranscriptRef.current(final.trim());
        }
      } else {
        setTranscript(interim);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "not-allowed") {
        setMicPermission("denied");
        setError("Microphone access denied. Please allow mic access and try again.");
      } else if (event.error !== "aborted" && event.error !== "no-speech") {
        setError(`Speech recognition error: ${event.error}`);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    try {
      recognition.start();
    } catch {
      setError("Failed to start speech recognition.");
      setIsListening(false);
    }
  }, [browserSupported, autoSend]);

  // --- TTS ---

  const stopSpeaking = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const speakText = useCallback(async (text: string) => {
    if (!text.trim()) return;

    // Cancel any in-flight TTS
    abortRef.current?.abort();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setIsSpeaking(true);

    try {
      const response = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });

      if (!response.ok) {
        // TTS failure is non-critical — silently fail
        setIsSpeaking(false);
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setIsSpeaking(false);
      };

      audio.onerror = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setIsSpeaking(false);
      };

      await audio.play();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // Intentional cancellation — not an error
      }
      setIsSpeaking(false);
    }
  }, []);

  // --- Toggle ---

  const toggleVoice = useCallback(() => {
    setVoiceEnabled((prev) => {
      if (prev) {
        // Turning off — stop everything
        recognitionRef.current?.abort();
        setIsListening(false);
        abortRef.current?.abort();
        if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current = null;
        }
        setIsSpeaking(false);
        setTranscript("");
        setError(null);
      }
      return !prev;
    });
  }, []);

  return {
    voiceEnabled,
    browserSupported,
    isListening,
    isSpeaking,
    transcript,
    micPermission,
    error,
    toggleVoice,
    startListening,
    stopListening,
    speakText,
    stopSpeaking,
  };
}
