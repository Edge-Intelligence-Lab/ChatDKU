"use client";

import { usePathname } from "next/navigation";
import { CornerRightUp, Mic } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/components/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/components/hooks/use-auto-resize-textarea";
import { io } from "socket.io-client";
import { API_ENDPOINTS } from "@/lib/constants";

export function AIInput({
  id = "ai-input",
  placeholder = "Type your message...",
  minHeight = 40,
  maxHeight = 200,
  onSubmit,
  onInputChange,
  className,
  thinkingMode,
  onThinkingModeChange,
  onEndpointChange,
  disabled = false,
}: {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  onInputChange?: (value: string) => void;
  onSubmit?: (value: string) => void;
  className?: string;
  thinkingMode?: boolean;
  searchMode?: string;
  onThinkingModeChange?: (value: boolean) => void;
  onEndpointChange?: (endpoint: string) => void;
  onSearchModeChange?: (value: string) => void;
  disabled?: boolean;
}) {
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight,
    maxHeight,
  });
  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isThinking, setIsThinking] = useState(thinkingMode || false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const socketRef = useRef<any>(null);

  const pathname = usePathname();
  const isDevRoute = pathname === "/dev" || pathname === "/dev/";

  const inputButtonStyle = cn(
    "flex items-center justify-around gap-1 p-2 text-sm min-w-[45px] min-h-[45px] rounded-4xl cursor-pointer border-transparent hover:border-foreground/10 border-1 hover:shadow-md active:text-foreground active:bg-foreground/10 transition-all duration-200",
  );

  useEffect(() => {
    // Check if running in browser and if media devices are supported
    if (typeof window !== "undefined") {
      if (!navigator?.mediaDevices?.getUserMedia) {
        console.warn("Media Devices API not supported in this browser");
      }
    }
  }, []);

  useEffect(() => {
    if (thinkingMode !== undefined && thinkingMode !== isThinking) {
      setIsThinking(thinkingMode);
    }
  }, [thinkingMode]);

  useEffect(() => {
    const wsUrl = API_ENDPOINTS.DICTATION_WS;
    const isSecure =
      wsUrl.startsWith("wss://") || wsUrl.startsWith("https://");

    socketRef.current = io(wsUrl, {
      transports: ["websocket"],
      secure: isSecure,
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      stopRecording();
    };
  }, []);

  const toggleThinkingMode = () => {
    if (disabled) return;
    const newValue = !isThinking;
    setIsThinking(newValue);
    onThinkingModeChange?.(newValue);
  };

  const startRecording = async () => {
    if (disabled) return;
    if (!navigator?.mediaDevices?.getUserMedia) {
      console.error("Media Devices API not supported");
      alert("Your browser does not support audio recording");
      return;
    }

    try {
      audioChunksRef.current = [];
      setIsRecording(true);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      audioStreamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      mediaRecorderRef.current = new MediaRecorder(stream, { mimeType });

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        try {
          const audioBlob = new Blob(audioChunksRef.current, {
            type: mimeType,
          });
          if (audioBlob.size > 0) {
            const buffer = await audioBlob.arrayBuffer();
            const uint8Array = new Uint8Array(buffer);
            socketRef.current.emit("audio_data", uint8Array);
          }
        } catch (error) {
          console.error("Error processing audio:", error);
        } finally {
          cleanupRecording();
        }
      };

      // Handle transcription responses
      socketRef.current.on("audio_transcribed", (data: { text: string }) => {
        setInputValue(data.text);
      });

      mediaRecorderRef.current.start();
      console.log("Recording started...");
    } catch (error) {
      console.error("Recording error:", error);
      setIsRecording(false);
      cleanupRecording();
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
      console.log("Recording stopped...");
    }
    setIsRecording(false);
  };

  const cleanupRecording = () => {
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
  };

  // Listen for external value changes through the input event
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const handleInput = (e: Event) => {
      if (disabled) return;
      const target = e.target as HTMLTextAreaElement;
      setInputValue(target.value);
      onInputChange?.(target.value);
      adjustHeight();
    };

    textarea.addEventListener("input", handleInput);
    return () => textarea.removeEventListener("input", handleInput);
  }, [textareaRef, adjustHeight, onInputChange, disabled]);

  const toggleRecording = async () => {
    if (disabled) return;
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  };

  const handleReset = () => {
    if (disabled) return;
    if (!inputValue.trim()) return;
    onSubmit?.(inputValue);
    setInputValue("");
    adjustHeight(true);
  };

  return (
    <div className={cn("w-full py-2", className)}>
      <div
        className={cn(
          "relative max-w-2xl w-full mx-auto",
          "rounded-3xl p-1 bg-background dark:bg-accent shadow-sm",
          "border border-foreground/10 ring-black/20 dark:ring-white/20",
          "overflow-y-auto resize-none",
          "focus-visible:ring-0 focus-visible:ring-offset-0",
          "transition-[height] duration-75 ease-in-out",
          "[&::-webkit-resizer]:hidden",
          "transition-all duration-200",
          inputValue
            ? "shadow-[0_0_12px_rgba(46,185,224,1)] animate-shadow-pulse"
            : "",
        )}
      >
        <style>
          {`
					@keyframes shadow-pulse {
						0% {
							box-shadow: 0 0 6px rgba(46 159 224 / 0.4);
						}
						50% {
							box-shadow: 0 0 9px #00DB6E5A;
						}
						100% {
							box-shadow: 0 0 6px rgba(46 159 224 / 0.4);
						}
					}
					.animate-shadow-pulse {
						animation: shadow-pulse 2s infinite;
					}
					`}
        </style>

        <div className="flex flex-row items-center">
          <Textarea
            autoFocus
            id={id}
            placeholder={!isRecording ? placeholder : "Listening..."}
            className={cn(
              "placeholder:text-black/40 dark:placeholder:text-white/40",
              "text-black dark:text-white text-wrap",
              "overflow-y-auto resize-none",
              "focus-visible:ring-0 focus-visible:ring-offset-0",
              "pt-2 border-none bg-transparent",
              `min-h-[${minHeight}px] max-h-[${maxHeight}px]`,
              "[&::-webkit-resizer]:hidden",
            )}
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => {
              if (disabled) return;
              const newValue = e.target.value;
              setInputValue(newValue);
              onInputChange?.(newValue);
              if (!newValue.trim()) {
                adjustHeight(true);
              } else {
                requestAnimationFrame(() => adjustHeight());
              }
            }}
            onKeyDown={(e) => {
              if (disabled) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleReset();
              }
            }}
            disabled={disabled}
          />
          {/* <div className={cn(isDevRoute && "hidden")}> */}
          <div>
            <button
              className={cn(
                inputButtonStyle,
                inputValue && "hidden",
                isRecording &&
                  "bg-red-500 border border-foreground/10 hover:mask-bg-secondary/50 text-secondary",
              )}
              onClick={toggleRecording}
              disabled={disabled}
            >
              <Mic className="cursor-pointer w-5 h-5" />
            </button>

            <button
              onClick={handleReset}
              type="button"
              className={cn(
                inputButtonStyle,
                inputValue
                  ? "opacity-100 scale-100"
                  : "hidden opacity-0 scale-50",
              )}
              disabled={disabled}
            >
              <CornerRightUp className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
