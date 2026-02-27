"use client";

import Image from "next/image";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

interface DynamicLogoProps {
	width?: number;
	height?: number;
}

const DynamicLogo: React.FC<DynamicLogoProps> = ({ width = 96, height = 96 }) => {
	const { resolvedTheme } = useTheme();
	const [currentTheme, setCurrentTheme] = useState<string | undefined>("light");

	// Calculate the inset value based on the width (using about 15% of width)
	const insetValue = Math.max(Math.floor(width * 0.05), 4);

	useEffect(() => {
		// Use resolvedTheme (which considers system preference) instead of theme
		setCurrentTheme(resolvedTheme);
	}, [resolvedTheme]);

	return (
		<div className="relative">
			{/* <div
				className={`absolute blur-lg animate-pulse dark:[background:linear-gradient(45deg,theme(colors.emerald.700),theme(colors.blue.900),theme(colors.green.900),theme(colors.blue.800))]`}
				style={{
					inset: `${insetValue}px`,
					borderRadius: "50%",
				}}
			/> */}
			<Image src="/logos/new_logo.svg" alt="Logo" className="relative" width={width} height={height} priority unoptimized loading="eager" />
		</div>
	);
};

export default DynamicLogo;
