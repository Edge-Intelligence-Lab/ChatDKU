"use client";

import { useState, ChangeEvent, FormEvent } from "react";
import {
	Sheet,
	SheetTrigger,
	SheetContent,
	SheetHeader,
	SheetFooter,
	SheetTitle,
	SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FolderPlus, Upload } from "lucide-react";
import { API_ENDPOINTS } from "@/lib/constants";

export function UploadSheet() {
	const [file, setFile] = useState<File | null>(null);
	const [status, setStatus] = useState<string | null>(null);
	const [open, setOpen] = useState(false);

	function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
		setFile(e.target.files?.[0] ?? null);
		setStatus(null);
	}

	async function handleSubmit(e: FormEvent) {
		e.preventDefault();
		if (!file) return setStatus("🚫 No file selected.");

		const formData = new FormData();
		formData.append("file_", file);

		try {
			setStatus("⏳ Uploading...");
			const res = await fetch(API_ENDPOINTS.FILE_UPLOAD, {
				method: "POST",
				body: formData,
			});
			if (!res.ok) {
				const err = await res.json();
				throw new Error(err.detail || JSON.stringify(err));
			}
			setStatus("✅ Upload succeeded!");
			// auto-close after a sec
			setTimeout(() => setOpen(false), 1000);
		} catch (err: any) {
			console.error(err);
			setStatus(`❌ Upload failed: ${err.message}`);
		}
	}

	return (
		<Sheet open={open} onOpenChange={setOpen}>
			<SheetTrigger asChild>
				<Button variant="inChatbox">
					<FolderPlus /> Upload
				</Button>
			</SheetTrigger>
			<SheetContent>
				<SheetHeader>
					<SheetTitle>Choose sources</SheetTitle>
					<SheetDescription>
						Add a .pdf file for ChatDKU to use as an extra source.
					</SheetDescription>
				</SheetHeader>

				<div className="px-2">
					<form onSubmit={handleSubmit} className="space-y-4 mt-4">
						<div>
							<Label htmlFor="file-input">Select file</Label>
							<Input
								id="file-input"
								type="file"
								accept=".pdf"
								onChange={handleFileChange}
								className="mt-1"
							/>
						</div>
						{status && <p className="text-sm">{status}</p>}
					</form>
				</div>

				<SheetFooter className="mt-6 flex justify-end space-x-2">
					<Button variant="outline" onClick={() => setOpen(false)}>
						Cancel
					</Button>
					<Button onClick={handleSubmit}>Upload</Button>
				</SheetFooter>
			</SheetContent>
		</Sheet>
	);
}
