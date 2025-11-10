import { useEffect, useState } from "react";
import { getUser } from "@/components/hooks/user";
import { getNewSession } from "@/lib/convosNew";

export default function WelcomeBanner() {
	const [me, setMe] = useState<{ eppn: string; displayName: string } | null>(
		null,
	);

	// useEffect(() => {
	// 	getUser().then(async (user) => {
	// 		setMe(user);
	// 		// Create a new session when user is successfully loaded
	// 		if (user) {
	// 			await getNewSession();
	// 		}
	// 	});
	// }, []);

	if (!me)
		return (
			<h1 className="text-xl md:text-2xl lg:text-3xl">Welcome to ChatDKU</h1>
		); // still loading or not logged in
	return (
		<h1 className="text-2xl lg:text-3xl">
			Welcome, {me.displayName || me.eppn.split("@")[0]}!
		</h1>
	);
}
