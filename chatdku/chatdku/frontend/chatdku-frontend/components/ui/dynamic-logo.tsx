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
    
    useEffect(() => {
        // Use resolvedTheme (which considers system preference) instead of theme
        setCurrentTheme(resolvedTheme);
    }, [resolvedTheme]);

    return (
        <div className="relative">
            <div className="absolute inset-4 rounded-full blur-lg animate-pulse [background:linear-gradient(45deg,theme(colors.emerald.600),theme(colors.blue.400),theme(colors.green.300),theme(colors.blue.500))] bg-opacity-20" />
            <Image
                src={currentTheme === "dark" ? "/logos/Dark-Logo.png" : "/logos/Light-Logo.png"}
                alt="Logo"
                className="relative w-{width} h-{height} transition-all duration-300 hover:scale-105"
                width={width}
                height={height}
            />
        </div>
    );
};

export default DynamicLogo;