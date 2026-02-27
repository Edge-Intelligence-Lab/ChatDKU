"use client";

import { FolderPlus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Checkbox } from "@/components/ui/checkbox";
// import { Badge } from "@components/ui/badge";

export function UserUploadSheet() {
	<Sheet>
		<SheetTrigger asChild>
			{/* <button className={inputButtonStyle}> */}
			<button>
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
						<input type="file" name="file" className="absolute inset-0 opacity-0 cursor-pointer" style={{ width: "100%", height: "100%" }} />
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
	</Sheet>;
}
