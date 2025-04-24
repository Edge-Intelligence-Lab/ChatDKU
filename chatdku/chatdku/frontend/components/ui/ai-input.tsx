"use client";

import { CornerRightUp, Mic } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/components/hooks/use-auto-resize-textarea";

export function AIInput({
  id = "ai-input",
  placeholder = "Type your message...",
  minHeight = 53,
  maxHeight = 200,
  onSubmit,
  className,
}: {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  onSubmit?: (value: string) => void;
  className?: string;
}) {
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight,
    maxHeight,
  });
  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    // Check if running in browser and if media devices are supported
    if (typeof window !== "undefined") {
      if (!navigator?.mediaDevices?.getUserMedia) {
        console.warn("Media Devices API not supported in this browser");
      }
    }
  }, []);

  const startRecording = async () => {
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
            console.log("Audio recording completed, but transcription is disabled");
          }
        } catch (error) {
          console.error("Error processing audio:", error);
        } finally {
          cleanupRecording();
        }
      };

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
      const target = e.target as HTMLTextAreaElement;
      setInputValue(target.value);
      adjustHeight();
    };

    textarea.addEventListener("input", handleInput);
    return () => textarea.removeEventListener("input", handleInput);
  }, [textareaRef, adjustHeight]);

  const toggleRecording = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  };

  const handleReset = () => {
    if (!inputValue.trim()) return;
    onSubmit?.(inputValue);
    setInputValue("");
    adjustHeight(true);
  };

  return (
    <div className={cn("w-full py-4", className)}>
      <div className="relative max-w-xl w-full mx-auto">
        <Textarea
          id={id}
          placeholder={placeholder}
          className={cn(
            "max-w-xl rounded-3xl pl-6 pr-16 backdrop-blur-md bg-white dark:bg-white/10",
            "placeholder:text-black/40 dark:placeholder:text-white/40",
            "border border-foreground/10 ring-black/20 dark:ring-white/20",
            "text-black dark:text-white text-wrap",
            "overflow-y-auto resize-none",
            "focus-visible:ring-0 focus-visible:ring-offset-0",
            "transition-[height] duration-75 ease-out",
            "leading-[1.2] py-[16px]",
            `min-h-[${minHeight}px] max-h-[${maxHeight}px]`,
            "[&::-webkit-resizer]:hidden",
            "shadow-[0_0_2px_rgba(16,185,129,0.1),0_0_16px_rgba(59,130,246,0.1)]",
            "transition-all duration-200",
            inputValue
              ? "shadow-[0_0_12px_rgba(46,205,199,0.3),0_0_12px_rgba(59,170,246,0.3)]"
              : ""
          )}
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => {
            const newValue = e.target.value;
            setInputValue(newValue);
            if (!newValue.trim()) {
              adjustHeight(true);
            } else {
              requestAnimationFrame(() => adjustHeight());
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleReset();
            }
          }}
        />

        <div
          className={cn(
            "absolute top-1/2 -translate-y-1/2 rounded-xl py-1 px-1 transition-all duration-200",
            inputValue ? "right-10" : "right-3",
            isRecording ? "bg-red-500/80 " : "bg-black/5 dark:bg-white/5"
          )}
        >
          <Mic
            className="cursor-pointer w-4 h-4 text-black/70 dark:text-white/70"
            onClick={toggleRecording}
          />
        </div>

        <button
          onClick={handleReset}
          type="button"
          className={cn(
            "absolute top-1/2 -translate-y-1/2 right-3",
            "rounded-xl bg-black/5 dark:bg-white/5 py-1 px-1",
            "transition-all duration-200",
            inputValue
              ? "opacity-100 scale-100"
              : "opacity-0 scale-95 pointer-events-none"
          )}
        >
          <CornerRightUp className="w-4 h-4 text-black/70 dark:text-white/70" />
        </button>
      </div>
    </div>
  );
}
