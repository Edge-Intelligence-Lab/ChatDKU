import { useEffect, useState } from "react";
import { getUser } from "@/lib/user";

export default function WelcomeBanner() {
	const [me, setMe] = useState<{ eppn: string; displayName: string } | null>(null);

	useEffect(() => {
		getUser().then(setMe);
	}, []);

	if (!me) return <h1 className="text-2xl lg:text-3xl">Welcome to ChatDKU</h1>; // still loading or not logged in
	return <h1 className="text-2xl lg:text-3xl">Welcome, {me.displayName || me.eppn.split("@")[0]}!</h1>;
}
