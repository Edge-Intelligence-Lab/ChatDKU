import { PlusCircle } from 'lucide-react';
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";
import { ModeToggle } from "@/components/ui/mode-toggle";
import DynamicLogo from "@/components/ui/dynamic-logo";

export function Navbar() {
  return (
    <NavigationMenu className="w-full max-w-[95vw] mx-auto flex justify-between items-center fixed top-4 left-1/2 -translate-x-1/2 z-10 shadow-sm border border-primary/5 rounded-2xl bg-background/85 backdrop-blur-sm">
      <div className="flex flex-row items-center p-4 space-x-2">
        <DynamicLogo width={30} height={30} />
        <h2 className="font-inter text-md md:text-xl lg:text-3xl font-bold">ChatDKU</h2>
      </div>
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuLink href="/about" className="lg:text-md">
            About
          </NavigationMenuLink>
        </NavigationMenuItem>
        <NavigationMenuItem>
          <NavigationMenuLink href="/" className="lg:text-md flex flex-row items-center">
            New Chat
            <PlusCircle className='size-4 text-primary-500' />
          </NavigationMenuLink>
        </NavigationMenuItem>
        <NavigationMenuItem className="mr-2 lg:ml-4">
          <ModeToggle />
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  );
} 