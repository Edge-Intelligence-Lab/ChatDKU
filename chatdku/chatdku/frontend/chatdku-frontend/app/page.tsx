"use client";

import Starter from "@/components/starter";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";

import Image from "next/image";
import { AIInput } from "@/components/ui/ai-input";

export default function Home() {
  return (
    <div className="p-4 flex flex-col">
      <NavigationMenu>
        <NavigationMenuList>
          <Image
            src={"/logos/Light-Logo.svg"}
            alt="ChatDKU Logo Light Variant"
            width={30}
            height={30}
          />
          <h2 className=" font-inter text-3xl font-bold">ChatDKU</h2>
          <NavigationMenuItem>
            <NavigationMenuLink href="/about">About</NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
            <NavigationMenuLink href="/">New session</NavigationMenuLink>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>
      <div className="flex flex-col items-center justify-center flex-grow">
        <Starter />
        <div className="space-y-8 min-w-[400px] absolute bottom-0 left-0 right-0 p-4">
          <div>
            <AIInput onSubmit={(value) => console.log("Submitted:", value)} />
            <p className="space-y-8 min-w-[400px] absolute bottom-0 left-0 right-0 p-1 text-sm text-muted-foreground">
              Developed by DKU Edge Intelligence Lab.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
