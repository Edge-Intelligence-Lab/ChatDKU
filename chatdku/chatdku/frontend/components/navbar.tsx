import { MessageCircleQuestion, SquarePen } from "lucide-react";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ModeToggle } from "@/components/ui/mode-toggle";
import DynamicLogo from "@/components/dynamic-logo";

export function Navbar() {
  return (
    <NavigationMenu className="w-full max-w-[98vw] mx-auto flex justify-between items-center fixed top-0 left-1/2 -translate-x-1/2 z-10 bg-background lg:bg-transparent">
      <div className="flex flex-row items-center">
          <div className="flex flex-row items-center p-3 pr-0 space-x-2">
            <DynamicLogo width={35} height={35} />
            <h2 className="font-inter text-xl md:text-xl font-bold">
              ChatDKU
              {/* <span className="font-inter text-xs md:text-sm lg:text-sm italic text-primary/20">dev</span> */}
            </h2>
          </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <NavigationMenuLink
                href="/about"
                className="lg:text-md flex flex-row items-center"
              >
                <MessageCircleQuestion className="size-4 text-primary-500" />
              </NavigationMenuLink>
            </TooltipTrigger>
            <TooltipContent>
              <p>About</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <NavigationMenuList>
        <NavigationMenuItem></NavigationMenuItem>
        <NavigationMenuItem>
        <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <NavigationMenuLink
            href="/"
            className="lg:text-md flex flex-row items-center"
          >
            <p className="hidden sm:block">New Chat</p>
            <SquarePen className="size-5 text-primary-500" />
          </NavigationMenuLink>
          </TooltipTrigger>
          <TooltipContent  className="sm:hidden">
          <p>New Chat</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
        </NavigationMenuItem>
        <NavigationMenuItem className="">
          {/* <ModeToggle /> */}
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  );
}
