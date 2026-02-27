"use client";

import { useState, useCallback, useEffect, SetStateAction } from "react";
import { marked } from "marked";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import {
	getNewSession,
	getCurrentSessionId,
	getStoredEndpoint,
	getSessionMessages,
} from "@/lib/convosNew";
import { AIInput } from "@/components/ui/ai-input";
import { Navbar } from "@/components/navbar";
import { PromptRecs } from "@/components/prompt_recs";
import WelcomeBanner from "@/components/WelcomeBanner";
import Side from "@/components/side";
import { DocumentManager } from "@/components/doc-manager";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type ChatPageProps = {
	isDev?: boolean;
};

const configureMarked = () => {
	marked.setOptions({
		breaks: true,
		gfm: true,
	});
};

const parseMarkdown = (content: string): string => {
	if (!content) return "";
	const cleanedContent = content.replace(/<think>[\s\S]*?<\/think>/gi, "");
	const parsed = marked.parse(cleanedContent) as any;
	if (typeof parsed?.then === "function") {
		return cleanedContent;
	}
	return typeof parsed === "string" && parsed.trim().length > 0
		? parsed
		: cleanedContent;
};

// Inject styles for the fancy AI loader once per document
const ensureSearchLoaderStyles = () => {
	if (typeof document === "undefined") return;
	if (document.getElementById("search-loader-style")) return;
	const style = document.createElement("style");
	style.id = "search-loader-style";
	style.innerHTML = `
    @keyframes iconCycle {
      0% { opacity: 0; transform: scale(0.92) translateY(2px) rotate(-2deg); }
      12% { opacity: 1; transform: scale(1) translateY(0) rotate(0deg); }
      28% { opacity: 1; transform: scale(1.02) translateY(0) rotate(0.5deg); }
      40% { opacity: 0; transform: scale(0.98) translateY(-1px) rotate(2deg); }
      100% { opacity: 0; }
    }
    @keyframes dotPulse {
      0%, 20% { opacity: 0.2; }
      50% { opacity: 1; }
      80%, 100% { opacity: 0.2; }
    }
    .cdku-loader .icon-cycle { animation: iconCycle 2400ms linear infinite; }
    .cdku-loader .icon-1 { animation-delay: 0ms; }
    .cdku-loader .icon-2 { animation-delay: 480ms; }
    .cdku-loader .icon-3 { animation-delay: 960ms; }
    .cdku-loader .icon-4 { animation-delay: 1440ms; }
    .cdku-loader .icon-5 { animation-delay: 1920ms; }
    .cdku-loader .dot { width: 3px; height: 3px; border-radius: 9999px; background-color: currentColor; display: inline-block; margin-left: 3px; opacity: 0.2; animation: dotPulse 1200ms ease-in-out infinite; }
    .cdku-loader .dot:nth-child(2) { animation-delay: 150ms; }
    .cdku-loader .dot:nth-child(3) { animation-delay: 300ms; }
  `;
	document.head.appendChild(style);
};

// Returns HTML string for the fancy loader using inline Lucide-like SVGs
const getSearchLoaderHTML = (): string => {
	const search =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="absolute inset-0 icon-cycle icon-1"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>';
	const fileSearch =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="absolute inset-0 icon-cycle icon-2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><circle cx="11.5" cy="14.5" r="2.5"/><path d="m13.3 16.3 1.7 1.7"/></svg>';
	const compass =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="absolute inset-0 icon-cycle icon-3"><circle cx="12" cy="12" r="10"/><path d="m16 8-4 8-4-4 8-4Z"/></svg>';
	const radar =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="absolute inset-0 icon-cycle icon-4"><path d="M21 12a9 9 0 1 1-9-9"/><path d="M22 12a10 10 0 1 1-10-10"/><path d="M14.31 8.69 21 2"/><circle cx="12" cy="12" r="0.5"/></svg>';
	const sparkles =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="absolute inset-0 icon-cycle icon-5"><path d="M12 3l1.9 3.9L18 9l-4.1 2.1L12 15l-1.9-3.9L6 9l4.1-2.1Z"/><path d="M20 17l.95 1.95L23 20l-1.95.95L20 23l-.95-2.05L17 20l2.05-.95Z"/><path d="M4 17l.95 1.95L7 20l-1.95.95L4 23l-.95-2.05L1 20l2.05-.95Z"/></svg>';

	return `
    <div class="cdku-loader flex items-center gap-2 sm:gap-2.5 text-foreground/80">
      <div class="relative inline-flex items-center justify-center align-middle" style="width:1em;height:1em;">
        ${search}
        ${fileSearch}
        ${compass}
        ${radar}
        ${sparkles}
      </div>
      <div class="text-xs sm:text-sm leading-none tracking-tight">
        <span class="opacity-80">Searching relevant documents</span>
        <span class="ml-1 inline-flex align-middle">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </span>
      </div>
    </div>
  `;
};

const streamText = async (
	text: string,
	elementContainer: HTMLElement,
	chunkDelayMs = 60,
) => {
	const cleanedText = text.replace(/<think>[\s\S]*?<\/think>/gi, "");

	// Ensure streaming styles exist (fade-in)
	if (!document.getElementById("stream-style")) {
		const style = document.createElement("style");
		style.id = "stream-style";
		style.innerHTML = `
      .stream-chunk { opacity: 0; transform: translateY(2px); transition: opacity 120ms ease-out, transform 120ms ease-out; }
      .stream-chunk.visible { opacity: 1; transform: translateY(0); }
    `;
		document.head.appendChild(style);
	}

	const streamContainer = document.createElement("div");
	streamContainer.className =
		"text-foreground  break-words overflow-wrap-anywhere markdown-content text-[0.9375rem]";
	elementContainer.appendChild(streamContainer);

	// Prefer paragraph chunks; fallback to sentences if only one paragraph
	const paragraphs = cleanedText
		.split(/\n{2,}/)
		.map((s) => s.trim())
		.filter((s) => s.length > 0);

	let chunks: string[] = [];
	if (paragraphs.length > 1) {
		chunks = paragraphs;
	} else {
		const sentences = cleanedText.match(/[^\r\n.!?]+[.!?]*(?:\s+|$)/g) || [
			cleanedText,
		];
		chunks = sentences.map((s) => s.trim()).filter((s) => s.length > 0);
	}

	// Stream each chunk as parsed markdown with a quick fade-in
	for (const chunk of chunks) {
		const chunkHTML = parseMarkdown(chunk);
		const chunkDiv = document.createElement("div");
		chunkDiv.className = "stream-chunk";
		chunkDiv.innerHTML = chunkHTML;
		streamContainer.appendChild(chunkDiv);

		// trigger transition
		// eslint-disable-next-line @typescript-eslint/no-unused-expressions
		chunkDiv.offsetHeight;
		requestAnimationFrame(() => {
			chunkDiv.classList.add("visible");
		});

		await new Promise((resolve) => setTimeout(resolve, chunkDelayMs));
	}

	return streamContainer;
};

export default function ChatPage({ isDev = false }: ChatPageProps) {
	const [showStarter, setShowStarter] = useState(true);
	const [isChatboxCentered, setIsChatboxCentered] = useState(true);
	const [chatHistoryId, setChatHistoryId] = useState("");
	const [currentSessionId, setCurrentSessionId] = useState<string>("");
	const [thinkingMode, setThinkingMode] = useState(false);
	const [searchMode, setSearchMode] = useState("");
	const [inputValue, setInputValue] = useState("");
	const [apiEndpoint, setApiEndpoint] = useState(getStoredEndpoint());
	const router = useRouter();
	const [showDocumentManager, setShowDocumentManager] = useState(false);
	const [isSessionLoading, setIsSessionLoading] = useState(true);
	const [sessionError, setSessionError] = useState<string | null>(null);

	useEffect(() => {
		configureMarked();
		let isMounted = true;

		const prepareSession = async () => {
			const termsAccepted = Cookies.get("terms_accepted");
			if (!termsAccepted) {
				setIsSessionLoading(false);
				router.push("/landing");
				return;
			}

			setSessionError(null);
			setIsSessionLoading(true);

			try {
				const storedSession = getCurrentSessionId();
				if (storedSession) {
					if (isMounted) {
						setCurrentSessionId(storedSession);
						setChatHistoryId(storedSession);
					}
				} else {
					const newSession = await getNewSession();
					if (!isMounted) return;
					if (newSession) {
						setCurrentSessionId(newSession);
						setChatHistoryId(newSession);
					} else {
						setSessionError(
							"We couldn't start a chat session. Please try again.",
						);
					}
				}
			} catch (error) {
				console.error("Error preparing session:", error);
				if (isMounted) {
					setSessionError(
						"We couldn't start a chat session. Please refresh the page.",
					);
				}
			} finally {
				if (isMounted) {
					setIsSessionLoading(false);
				}
			}
		};

		void prepareSession();

		return () => {
			isMounted = false;
		};
	}, [router]);

	const handleRetrySession = useCallback(async () => {
		setSessionError(null);
		setIsSessionLoading(true);
		try {
			const newSessionId = await getNewSession();
			if (newSessionId) {
				setCurrentSessionId(newSessionId);
				setChatHistoryId(newSessionId);
			} else {
				setSessionError("We couldn't start a chat session. Please try again.");
			}
		} catch (error) {
			console.error("Error retrying session:", error);
			setSessionError("We couldn't start a chat session. Please try again.");
		} finally {
			setIsSessionLoading(false);
		}
	}, []);

	const isSessionReady =
		Boolean(currentSessionId) && !isSessionLoading && !sessionError;
	const sessionPlaceholder = isSessionLoading
		? "Preparing your chat session..."
		: sessionError
			? "Session unavailable. Please try again."
			: "Type your message...";

	const handleFeedback = useCallback(
		async (userInput: any, answer: any, reason: any) => {
			try {
				await fetch("/api/feedback", {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify({
						userInput,
						botAnswer: answer,
						feedbackReason: reason,
						chatHistoryId,
					}),
				});
			} catch (error) {
				console.error("Failed to save feedback:", error);
			}
		},
		[chatHistoryId],
	);

	const addMessageToChat = useCallback(
		(role: string, content: any, className: any, shouldStream = false) => {
			const chatLog = document.getElementById("chat-log");
			const messageElement = document.createElement("div");
			const isUser = role === "user";
			messageElement.className = `flex ${isUser ? "justify-end" : ""} w-full`;

			if (isUser || !shouldStream) {
				const isRawHtml =
					typeof content === "string" && content.startsWith("<");
				const sanitizedContent = content
					? isRawHtml
						? content
						: parseMarkdown(content).trim()
					: "";

				messageElement.innerHTML = `
        <div class="flex flex-col ${isUser ? (isDev ? "items-end max-w-[85%] sm:max-w-[80%]" : "items-end max-w-[95%] sm:max-w-[85%]") : "items-start w-full sm:max-w-[85%]"}">
          <div class="flex flex-col ${isUser ? "lg:flex-row-reverse" : "lg:flex-row"} gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
            ${
							isUser
								? ""
								: '<div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-transparent flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>'
						}
            <div class="${isUser ? "text-right" : "text-left"} overflow-hidden">
              <div class="text-foreground break-words overflow-wrap-anywhere markdown-content ${!isUser ? "text-[0.9375rem]" : ""}">${sanitizedContent}</div>
            </div>
          </div>
        </div>
      `;
				chatLog?.appendChild(messageElement);
				chatLog?.scrollTo(0, chatLog.scrollHeight);
				return messageElement.querySelector(".flex.flex-col");
			} else {
				messageElement.innerHTML = `
        <div class="flex flex-col items-start w-full sm:max-w-[85%]">
          <div class="flex flex-col lg:flex-row gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
            <div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-transparent flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>
            <div class="text-left overflow-hidden" id="stream-container">
            </div>
          </div>
        </div>
      `;
				chatLog?.appendChild(messageElement);
				chatLog?.scrollTo(0, chatLog.scrollHeight);

				const streamContainer = messageElement.querySelector(
					"#stream-container",
				) as HTMLElement;
				if (streamContainer) {
					streamText(content, streamContainer, isDev ? 90 : 60);
				}

				return messageElement.querySelector(".flex.flex-col");
			}
		},
		[isDev],
	);

	// Inserts a special assistant message rendered from raw HTML (no markdown parsing)
	const addAssistantRawHtml = useCallback((html: string, className: string) => {
		const chatLog = document.getElementById("chat-log");
		const messageElement = document.createElement("div");
		messageElement.className = "flex w-full";
		messageElement.innerHTML = `
      <div class="flex flex-col items-start w-full sm:max-w-[85%]">
        <div class="flex flex-col lg:flex-row gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
          <div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-transparent flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>
          <div class="text-left overflow-hidden">
            ${html}
          </div>
        </div>
      </div>
    `;
		chatLog?.appendChild(messageElement);
		chatLog?.scrollTo(0, chatLog.scrollHeight);
		return messageElement.querySelector(".flex.flex-col");
	}, []);

	return (
		<>
			<Side
				onDocumentManager={() => {
					setShowDocumentManager(true);
				}}
				onEndpointChange={setApiEndpoint}
				currentEndpoint={apiEndpoint}
				currentSessionId={currentSessionId}
				disabled={!isSessionReady}
				onNewChat={async () => {
					setShowStarter(true);
					setIsChatboxCentered(true);
					setSessionError(null);
					setIsSessionLoading(true);
					try {
						const newSessionId = await getNewSession();
						if (newSessionId) {
							setCurrentSessionId(newSessionId);
							setChatHistoryId(newSessionId);
							const chatLog = document.getElementById("chat-log");
							if (chatLog) {
								chatLog.innerHTML = "";
							}
						} else {
							setSessionError(
								"We couldn't start a new chat session. Please try again.",
							);
						}
					} catch (error) {
						console.error("Error starting new chat:", error);
						setSessionError(
							"We couldn't start a new chat session. Please try again.",
						);
					} finally {
						setIsSessionLoading(false);
					}
				}}
				onConversationSelect={async (sessionId) => {
					setShowStarter(false);
					setIsChatboxCentered(false);
					setCurrentSessionId(sessionId);
					setChatHistoryId(sessionId);

					const chatLog = document.getElementById("chat-log");
					if (chatLog) {
						chatLog.innerHTML = "";
					}

					const messages = await getSessionMessages(sessionId);
					messages.forEach((msg) => {
						addMessageToChat(
							msg.role.toLowerCase(),
							msg.content,
							"text-sm",
							false,
						);
					});
				}}
			/>
			<div className="flex flex-col min-h-screen relative selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
				{(isSessionLoading || sessionError) && (
					<div className="absolute inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-background/85 backdrop-blur-sm">
						{isSessionLoading ? (
							<>
								<Loader2 className="h-8 w-8 animate-spin text-foreground" />
								<p className="text-sm text-muted-foreground">
									Preparing your chat session...
								</p>
							</>
						) : (
							<>
								<p className="text-sm text-muted-foreground max-w-xs text-center">
									{sessionError}
								</p>
								<Button onClick={handleRetrySession}>Try again</Button>
							</>
						)}
					</div>
				)}
				<header className="sticky top-0 z-20 w-full">
					<Navbar />
				</header>

				<main className="flex-1 w-full flex flex-col items-center pt-16">
					<div
						id="chat-log"
						className="w-full max-w-3xl mx-auto space-y-4 p-4 pb-42 overflow-y-auto"
					></div>
				</main>

				<div
					className={`w-full max-w-[95vw] p-2 pt-0 transition-all duration-300 ${
						isChatboxCentered
							? "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
							: "fixed bottom-0 left-1/2 -translate-x-1/2 rounded-t-3xl backdrop-blur-md md:backdrop-blur-none z-10"
					}`}
				>
					{showStarter && (
						<div className="w-full flex justify-center">
							<div className="flex flex-col items-center p-4 w-4/5 md:max-w-1/2 sm:max-w-4/5">
								<WelcomeBanner />
							</div>
						</div>
					)}
					<div>
						<AIInput
							disabled={!isSessionReady}
							placeholder={sessionPlaceholder}
							thinkingMode={thinkingMode}
							onThinkingModeChange={(value) => setThinkingMode(value)}
							searchMode={searchMode}
							onSearchModeChange={(value: SetStateAction<string>) =>
								setSearchMode(value)
							}
							onInputChange={(value) => setInputValue(value)}
							onEndpointChange={setApiEndpoint}
							onSubmit={async (value) => {
								if (!value.trim()) return;

								setShowStarter(false);
								setIsChatboxCentered(false);

								const activeSessionId =
									currentSessionId || getCurrentSessionId() || "";
								if (!activeSessionId) {
									setSessionError(
										"We couldn't find an active chat session. Please try again.",
									);
									return;
								}

								if (currentSessionId !== activeSessionId) {
									setCurrentSessionId(activeSessionId);
								}
								if (chatHistoryId !== activeSessionId) {
									setChatHistoryId(activeSessionId);
								}

								addMessageToChat(
									"user",
									value,
									"bg-muted/50 dark:bg-muted/50 text-sm",
								);

								ensureSearchLoaderStyles();
								const botMessage = addAssistantRawHtml(
									getSearchLoaderHTML(),
									"text-sm",
								);

								try {
									let response: any;
									if (value.trim().toLowerCase() === "test") {
										response = await fetch("/mdtest.md");
									} else {
										response = await fetch(apiEndpoint, {
											method: "POST",
											headers: { "Content-Type": "application/json" },
											body: JSON.stringify({
												messages: [{ role: "user", content: value }],
												chatHistoryId: activeSessionId,
												mode: thinkingMode ? "agent" : "",
												searchMode: searchMode,
											}),
										});
									}

									if (!response.ok) throw new Error("Failed to fetch response");

									if (botMessage) {
										botMessage.remove();
									}

									const messageDiv = addMessageToChat(
										"assistant",
										"",
										"text-sm",
										true,
									);

									const streamContainer =
										messageDiv?.querySelector("#stream-container");
									if (!streamContainer)
										throw new Error("Failed to create stream container");

									const data = await response.text();
									await streamText(
										data,
										streamContainer as HTMLElement,
										isDev ? 90 : 60,
									);

									if (messageDiv) {
										const feedbackDiv = document.createElement("div");
										feedbackDiv.className = "ml-4 mb-2";
										const feedbackContent = `
                    <div class="flex items-center gap-2 text-left">
                      <span class="text-sm text-muted-foreground">Was this response helpful?</span>
                      <button class="feedback-yes px-2 py-1 text-sm rounded-md bg-secondary/50 hover:bg-secondary">Yes</button>
                      <button class="feedback-no px-2 py-1 text-sm rounded-md bg-secondary/50 transition-all duration-300 hover:bg-red-600 hover:text-white">No</button>
                    </div>
                  `;
										feedbackDiv.innerHTML = feedbackContent;

										const yesButton =
											feedbackDiv.querySelector(".feedback-yes");
										const noButton = feedbackDiv.querySelector(".feedback-no");

										yesButton?.addEventListener("click", () => {
											handleFeedback(value, data, "helpful");
											feedbackDiv.innerHTML =
												'<span class="text-sm text-muted-foreground">Thanks for your feedback!</span>';
										});

										noButton?.addEventListener("click", () => {
											feedbackDiv.innerHTML = `
                      <div class="fixed inset-0 bg-background/80 backdrop-blur-sm z-50">
                        <div class="fixed inset-0 flex items-center justify-center">
                          <div class="dialog bg-background border shadow-lg rounded-lg w-[90%] max-w-md p-6">
                            <h3 class="text-lg font-semibold mb-4">Sorry to hear that. Can you tell us why?</h3>
                            <div class="feedback-options space-y-2" id="reason-options">
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_correct">Not Correct</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_clear">Not Clear</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_relevant">Not Relevant</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="other">Other</button>
                            </div>
                            <textarea id="custom-reason" class="w-full mt-4 p-2 rounded-md border bg-background text-foreground hidden" rows="5" placeholder="Please describe the issue"></textarea>
                            <div class="flex justify-end mt-6 space-x-2">
                              <button id="submit-feedback" class="btn px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90">Submit</button>
                              <button id="cancel-feedback" class="btn px-4 py-2 text-sm rounded-md bg-secondary text-secondary-foreground hover:bg-destructive hover:text-destructive-foreground">Cancel</button>
                            </div>
                          </div>
                        </div>
                      </div>
                    `;

											const optionButtons =
												feedbackDiv.querySelectorAll(".reason-btn");
											const customReason = feedbackDiv.querySelector(
												"#custom-reason",
											) as HTMLTextAreaElement;
											const submitBtn =
												feedbackDiv.querySelector("#submit-feedback");
											const cancelBtn =
												feedbackDiv.querySelector("#cancel-feedback");

											let selectedReason: string | null = null;

											optionButtons.forEach((btn) => {
												btn.addEventListener("click", () => {
													selectedReason =
														(btn as HTMLElement).dataset.reason || null;

													optionButtons.forEach((b) =>
														b.classList.remove("bg-secondary", "text-white"),
													);
													btn.classList.add("bg-secondary", "text-black");

													if (selectedReason === "other") {
														customReason.classList.remove("hidden");
													} else {
														customReason.classList.add("hidden");
													}
												});
											});

											submitBtn?.addEventListener("click", () => {
												if (!selectedReason) return;

												let reasonToSend =
													selectedReason === "other"
														? customReason.value.trim()
														: selectedReason;

												if (selectedReason === "other" && !reasonToSend) {
													customReason.classList.add("border-destructive");
													customReason.placeholder = "Please write something!";
													return;
												}

												handleFeedback(value, data, reasonToSend);
												feedbackDiv.innerHTML = `<span class=\"text-sm text-muted-foreground\">Thanks for your feedback!</span>`;
											});

											cancelBtn?.addEventListener("click", () => {
												feedbackDiv.innerHTML = `<span class=\"text-sm text-muted-foreground\">Feedback canceled.</span>`;
											});
										});

										messageDiv.appendChild(feedbackDiv);
									}
								} catch (error) {
									if (botMessage) {
										botMessage.remove();
									}
									addMessageToChat(
										"assistant",
										`Error: ${error instanceof Error ? error.message : "An unknown error occurred"}`,
										"bg-destructive/10 dark:bg-destructive/20",
									);
								}
							}}
						/>
						{isChatboxCentered && (
							<div
								className={`transition-all duration-300 ${inputValue ? "opacity-0 max-h-0 overflow-hidden" : "opacity-100 max-h-96"}`}
							>
								<PromptRecs
									onPromptSelect={(prompt) => {
										const aiInput = document.getElementById(
											"ai-input",
										) as HTMLTextAreaElement;
										if (aiInput) {
											aiInput.value = prompt;
											const inputEvent = new Event("input", { bubbles: true });
											aiInput.dispatchEvent(inputEvent);
											const enterEvent = new KeyboardEvent("keydown", {
												key: "Enter",
												code: "Enter",
												bubbles: true,
												cancelable: true,
												shiftKey: false,
											});
											aiInput.dispatchEvent(enterEvent);
										}
									}}
								/>
							</div>
						)}
					</div>
					{!isChatboxCentered && (
						<p className="text-center text-[11px]/3 pb-1 sm:py-0 sm:leading-1 leading-3 tracking-tight text-muted-foreground drop-shadow-background drop-shadow-xl">
							{isDev
								? "This is an unreleased testing site for development purposes only."
								: "AI responses may contain errors. Please verify with your advisor/and or Academic Services if anything is unclear."}
						</p>
					)}
				</div>
				<DocumentManager
					open={showDocumentManager}
					onOpenChange={setShowDocumentManager}
				/>
			</div>
		</>
	);
}
