"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

interface PromptRecsProps {
	onPromptSelect: (prompt: string) => void;
	onSubmit?: () => void; // Add an optional onSubmit prop
}

const allPrompts = [
	{
		text: "What majors are available at Duke Kunshan University?",
		icon: "📚",
	},
	{
		text: "How can I declare my major?",
		icon: "🎓",
	},
	{
		text: "Tell me about the Common Core curriculum.",
		icon: "🌟",
	},
	{
		text: "What are the graduation requirements?",
		icon: "🎯",
	},
	{
		text: "Can I switch my major later on? How?",
		icon: "📝",
	},
	{
		text: "What academic resources are available?",
		icon: "📖",
	},
	{
		text: "What are the courses of Applied Mathematics?",
		icon: "📊",
	},
	{
		text: "How can I change my major?",
		icon: "🔄",
	},
	{
		text: "Tell me about study abroad opportunities.",
		icon: "✈️",
	},
	{
		text: "How can I get assistance from Residence Life?",
		icon: "🏠",
	},
	{
		text: "What should I do if I have an IT issue at DKU?",
		icon: "💻",
	},
	{
		text: "What resources are available for mental health support at DKU?",
		icon: "🧠",
	},
	{
		text: "How can I find an internship with the help of DKU career services?",
		icon: "💼",
	},
	{
		text: "What career services are offered, including resume workshops and job fairs?",
		icon: "📄",
	},
	{
		text: "What scholarships and grants are available, and what are the eligibility criteria?",
		icon: "🎓",
	},
	{
		text: "What is the process for applying for financial aid?",
		icon: "💰",
	},
	{
		text: "What are the resources for students interested in entrepreneurship?",
		icon: "🚀",
	},
	{
		text: "What student organizations and clubs are available?",
		icon: "🤝",
	},
	{
		text: "Are there work-study programs available, and how can students apply?",
		icon: "📋",
	},
	{
		text: "Are there recreational and fitness facilities on campus?",
		icon: "🏋️",
	},
	{
		text: "What are the rules regarding library rooms?",
		icon: "📚",
	},
	{
		text: "What health services are provided on campus?",
		icon: "🏥",
	},
	{
		text: "Who should I contact in case of an emergency at DKU?",
		icon: "🚨",
	},
	{
		text: "What are the Distribution Requirements?",
		icon: "📋",
	},
	{
		text: "What's Common Core?",
		icon: "🎯",
	},
	{
		text: "Can I make changes to my course schedule after registration?",
		icon: "🔄",
	},
	{
		text: "How many credits can I take in a semester?",
		icon: "📊",
	},
	{
		text: "Will courses that I withdrew show on my transcript?",
		icon: "📝",
	},
	{
		text: "What letter grade would be considered CR and what would be considered NC?",
		icon: "📈",
	},
	{
		text: "Can I repeat a course in which the grade of the record is CR/NC?",
		icon: "🔁",
	},
	{
		text: "What is the process for major declaration?",
		icon: "📑",
	},
	{
		text: "When can I declare a major?",
		icon: "📅",
	},
	{
		text: "Can I request a Leave of Absence for military service?",
		icon: "🎖️",
	},
	{
		text: "How do I request a Medical Leave of Absence?",
		icon: "🏥",
	},
	{
		text: "Who should I consult if I have concerns related to my registration?",
		icon: "👨‍💼",
	},
	{
		text: "How do I clear my probationary status?",
		icon: "⚠️",
	},
	{
		text: "How many credits can I transfer from Study Abroad?",
		icon: "✈️",
	},
	{
		text: "What is the scoring standard for NSPHST and graduation requirement?",
		icon: "🎯",
	},
];

export function PromptRecs({ onPromptSelect, onSubmit }: PromptRecsProps) {
	// Start with empty array to avoid hydration mismatch
	const [selectedPrompts, setSelectedPrompts] = useState<typeof allPrompts>([]);

	// Select random prompts only on client side after component mounts
	useEffect(() => {
		const shuffled = [...allPrompts].sort(() => Math.random() - 0.5);
		setSelectedPrompts(shuffled.slice(0, 3));
	}, []);

	const handlePromptClick = (promptText: string) => {
		// First set the prompt text
		onPromptSelect(promptText);

		// Then immediately try to submit the form directly
		setTimeout(() => {
			// Find input fields
			const inputs = document.querySelectorAll('input[type="text"], textarea');

			// Try to simulate Enter keypress on the input field
			if (inputs.length > 0) {
				const lastInput = inputs[inputs.length - 1] as HTMLElement;
				lastInput.focus();

				// Create and dispatch an Enter key event
				const enterEvent = new KeyboardEvent("keydown", {
					bubbles: true,
					cancelable: true,
					key: "Enter",
					code: "Enter",
					keyCode: 13,
					which: 13,
				});

				lastInput.dispatchEvent(enterEvent);
				console.log("Enter key event dispatched on input");
			}

			// Direct approach - event on send button
			const sendButton = document.querySelector(
				'button[aria-label="Send message"], button:has(svg[data-icon="paper-plane"]), button:has(svg[data-testid="send-icon"])'
			);
			if (sendButton instanceof HTMLElement) {
				sendButton.click();
				console.log("Send button clicked");
			}

			// If onSubmit was provided, call it as well
			if (onSubmit) {
				onSubmit();
				console.log("onSubmit called");
			}
		}, 10);
	};

	return (
		<div className="flex flex-col sm:flex-row gap-2 pt-2 justify-center w-full mx-auto">
			{selectedPrompts.map((prompt, index) => (
				<Button
					key={`${prompt.text}-${index}`}
					variant="outline"
					className="flex items-center shadow-none gap-2 px-4 py-2 text-xs rounded-3xl transition-colors w-full md:max-w-[280px] sm:max-w-[230px] h-auto whitespace-normal"
					onClick={() => handlePromptClick(prompt.text)}
				>
					<span className="text-lg flex-shrink-0">{prompt.icon}</span>
					<span className="text-left break-words">{prompt.text}</span>
				</Button>
			))}
		</div>
	);
}
