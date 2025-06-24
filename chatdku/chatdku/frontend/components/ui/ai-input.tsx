"use client";

import { usePathname } from "next/navigation";
import { Brain, CornerRightUp, FileBox, FolderPlus, Mic, PlusCircle, Trash, Trash2, Upload, Wrench, X } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/components/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/components/hooks/use-auto-resize-textarea";
import { io } from "socket.io-client";
import { ComboBoxResponsive } from "./combobox";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "./badge";

export function AIInput({
	id = "ai-input",
	placeholder = "Type your message...",
	minHeight = 42,
	maxHeight = 200,
	onSubmit,
	onInputChange,
	className,
	thinkingMode,
	onThinkingModeChange,
	onEndpointChange,
}: {
	id?: string;
	placeholder?: string;
	minHeight?: number;
	maxHeight?: number;
	onInputChange?: (value: string) => void;
	onSubmit?: (value: string) => void;
	className?: string;
	thinkingMode?: boolean;
	onThinkingModeChange?: (value: boolean) => void;
	onEndpointChange?: (endpoint: string) => void;
}) {
	const { textareaRef, adjustHeight } = useAutoResizeTextarea({
		minHeight,
		maxHeight,
	});
	const [isAgentic] = useState(false);
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
		"flex items-center justify-around gap-1 p-2 text-sm min-w-[45px] min-h-[45px] rounded-4xl cursor-pointer border-transparent hover:border-foreground/10 border-1 hover:shadow-md active:text-foreground active:bg-foreground/10 transition-all duration-200"
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
		socketRef.current = io("https://chatdku.dukekunshan.edu.cn:8007", {
			transports: ["websocket"],
			secure: true,
		});

		return () => {
			if (socketRef.current) {
				socketRef.current.disconnect();
			}
			stopRecording();
		};
	}, []);

	const toggleThinkingMode = () => {
		const newValue = !isThinking;
		setIsThinking(newValue);
		onThinkingModeChange?.(newValue);
	};

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

			const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";

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
			const target = e.target as HTMLTextAreaElement;
			setInputValue(target.value);
			onInputChange?.(target.value);
			adjustHeight();
		};

		textarea.addEventListener("input", handleInput);
		return () => textarea.removeEventListener("input", handleInput);
	}, [textareaRef, adjustHeight, onInputChange]);

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
					inputValue ? "shadow-[0_0_12px_rgba(46,185,224,1)] animate-shadow-pulse" : ""
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
				<Textarea
					autoFocus
					id={id}
					placeholder={placeholder}
					className={cn(
						"placeholder:text-black/40 dark:placeholder:text-white/40",
						"text-black dark:text-white text-wrap",
						"overflow-y-auto resize-none",
						"focus-visible:ring-0 focus-visible:ring-offset-0",
						"pt-3 border-none bg-transparent",
						`min-h-[${minHeight}px] max-h-[${maxHeight}px]`,
						"[&::-webkit-resizer]:hidden"
					)}
					ref={textareaRef}
					value={inputValue}
					onChange={(e) => {
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
						if (e.key === "Enter" && !e.shiftKey) {
							e.preventDefault();
							handleReset();
						}
					}}
				/>
				<div className="flex flex-row justify-between">
					<div className="flex flex-row gap-x-1">
						{/* Thinking mode toggle button */}
						{!isDevRoute && (
							<button className={cn(inputButtonStyle, isThinking && "bg-primary text-primary-foreground")} onClick={toggleThinkingMode}>
								<Brain className="w-5 h-5" />
								<span className={cn("")}>Deep Think</span>
							</button>
						)}

						{isDevRoute && (
							<div className={inputButtonStyle}>
								<ComboBoxResponsive inputValue={inputValue} onEndpointChange={onEndpointChange ?? (() => {})} />
							</div>
						)}

						{isDevRoute && (
							<Sheet>
								<SheetTrigger asChild>
									<button className={inputButtonStyle}>
										<FolderPlus className="w-5 h-5" />
										Sources
									</button>
								</SheetTrigger>
								<SheetContent>
									<SheetHeader>
										<SheetTitle>Edit Sources</SheetTitle>
										<SheetDescription>Choose which sources ChatDKU can examine to answer your next question.</SheetDescription>
									</SheetHeader>
									<div className="flex flex-col gap-6 px-4">
										<div className="flex items-center cursor-pointer gap-2">
											<Checkbox id="dku_files" />
											<Label htmlFor="dku_files">Search DKU files, websites, and documents</Label>
										</div>
										<div className="flex items-center cursor-pointer gap-2">
											<Checkbox id="userFile1" className="cursor-pointer" />
											<Label htmlFor="userFile1" className="flex items-center cursor-pointer break-all gap-2 ">
												dku_library_policy_2025_final_final_edited (1).pdf
											</Label>
											<Button variant="destructive" className="rounded-full w-10 h-10">
												<Trash2 className="w-4 h-4" />
											</Button>
										</div>
										<div className="flex items-center cursor-pointer gap-2">
											<Checkbox id="userFile2" className="cursor-pointer" />
											<Label htmlFor="userFile2" className="flex items-center cursor-pointer break-all gap-2 ">
												dku_library_policy_2025_final_final_edited_by_anar (1).docx
											</Label>
											<Button variant="destructive" className="rounded-full w-10 h-10">
												<Trash2 className="w-4 h-4" />
											</Button>
										</div>
										<div className="flex items-center cursor-pointer gap-2">
											<Button className="relative w-full flex items-center gap-2 px-3 py-2">
												<Upload className="w-5 h-5" />
												<span>Add New Document</span>
												<input
													type="file"
													name="file"
													className="absolute inset-0 opacity-0 cursor-pointer"
													style={{ width: "100%", height: "100%" }}
												/>
											</Button>
										</div>
										<div className="flex items-center gap-2 hover:cursor-not-allowed">
											<Button className="w-full " variant="secondary" disabled>
												Maximum 3 documents reached.
											</Button>
										</div>
									</div>
									<SheetFooter>
										<Button type="submit">Save changes</Button>
										<SheetClose asChild>
											<Button variant="outline">Close</Button>
										</SheetClose>
									</SheetFooter>
								</SheetContent>
							</Sheet>
						)}
					</div>
					<div>
						<button
							className={cn(
								inputButtonStyle,
								inputValue && "hidden",
								isRecording && "bg-red-500 border border-foreground/10 hover:mask-bg-secondary/50 text-secondary"
							)}
							onClick={toggleRecording}
						>
							<Mic className="cursor-pointer w-5 h-5" />
						</button>

						<button
							onClick={handleReset}
							type="button"
							className={cn(inputButtonStyle, inputValue ? "opacity-100 scale-100" : "hidden opacity-0 scale-50")}
						>
							<CornerRightUp className="w-5 h-5" />
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}
