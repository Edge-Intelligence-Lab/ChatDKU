import Image from "next/image";
import { useTheme } from "next-themes";

interface DynamicLogoProps {
    width?: number;
    height?: number;
}

const DynamicLogo: React.FC<DynamicLogoProps> = ({ width = 96, height = 96 }) => {
    const { theme } = useTheme();

    return (
        <div>
            <Image
                src={theme === "dark" ? "/logos/Dark-Logo.png" : "/logos/Light-Logo.png"} // Dynamic logo based on theme
                alt="Logo"
                className="w-12 h-12"
                width={width}
                height={height}
            />
        </div>
    );
};

export default DynamicLogo;