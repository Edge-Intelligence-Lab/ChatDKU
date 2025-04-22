import { MessageCircleQuestion, PlusCircle } from "lucide-react";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";
import { ModeToggle } from "@/components/ui/mode-toggle";
import DynamicLogo from "@/components/dynamic-logo";

export function Navbar() {
  return (
    <NavigationMenu className="w-full max-w-[95vw] mx-auto flex justify-between items-center fixed top-0 left-1/2 -translate-x-1/2 z-10 bg-background lg:bg-transparent">
      <NavigationMenuLink href="/" className="backdrop-blur-md rounded-br-2xl rounded-tr-none hover:bg-transparent p-0">
        <div className="flex flex-row items-center p-4 space-x-2">
          <DynamicLogo width={35} height={35} />
          <h2 className="font-inter text-xl md:text-2xl lg:text-3xl font-bold">
            ChatDKU <span className="font-inter text-xs md:text-sm lg:text-sm italic">dev preview</span>
          </h2>
        </div>
      </NavigationMenuLink>
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuLink href="/about" className="lg:text-md">
            <MessageCircleQuestion className="size-5 text-primary-500" />
          </NavigationMenuLink>
        </NavigationMenuItem>
        <NavigationMenuItem>
          <NavigationMenuLink
            href="/"
            className="lg:text-md flex flex-row items-center"
          >
            {/* New Chat */}
            <PlusCircle className="size-5 text-primary-500" />
          </NavigationMenuLink>
        </NavigationMenuItem>
        <NavigationMenuItem className="">
          <ModeToggle />
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  );
}
