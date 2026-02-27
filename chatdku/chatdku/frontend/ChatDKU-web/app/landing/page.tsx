"use client";
import About from "@/components/about";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { getNewSession } from "@/lib/convosNew";
import { useState } from "react";
import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";

export default function AboutPage() {
	const [termsAccepted, setTermsAccepted] = useState(false);

	const router = useRouter();

	const handleProceed = async () => {
		if (termsAccepted) {
			// Set cookie for terms acceptance - expires in 60 days
			Cookies.set("terms_accepted", "true", { expires: 60 });
			// Navigate to the main app
			try {
				await getNewSession();
			} catch (e) {
				console.error("session create failed");
			}
			router.push("/");
		}
	};

	return (
		<div>
			<div className="flex flex-col items-center">
				{/* Without showing "Credits" button */}
				<About showCredits={false} /> 
				<div className="flex flex-col items-center">
					<div className="flex items-center space-x-2">
						<Checkbox
							id="terms"
							checked={termsAccepted}
							className="cursor-pointer"
							onCheckedChange={(checked) => setTermsAccepted(checked === true)}
						/>
						<label
							htmlFor="terms"
							className="cursor-pointer text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
						>
							Accept Terms and Conditions
						</label>
					</div>

					<p className="text-xs text-muted-foreground mt-2">
						We save a cookie to remember your preferences.
					</p>

					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild className="my-8">
								<div>
									<Button
										variant="default"
										className="rounded-full"
										disabled={!termsAccepted}
										onClick={handleProceed}
									>
										<p>
											Proceed to <span className="font-bold">ChatDKU</span>
										</p>
									</Button>
								</div>
							</TooltipTrigger>
							{!termsAccepted && (
								<TooltipContent>
									<p>Please accept the Terms and Conditions to use ChatDKU</p>
								</TooltipContent>
							)}
						</Tooltip>
					</TooltipProvider>
				</div>
			</div>
		</div>
	);
}
