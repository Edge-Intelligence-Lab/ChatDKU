"use client";
import { MessageCircleQuestion, SquarePen } from "lucide-react";
import { usePathname } from "next/navigation";
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

// import { ModeToggle } from "@/components/ui/mode-toggle";
import DynamicLogo from "@/components/dynamic-logo";
import { Badge } from "@/components/ui/badge";
import { ModeToggle } from "./ui/mode-toggle";

export function Navbar() {
	const pathname = usePathname();
	const isDevRoute = pathname === "/dev" || pathname === "/dev/";
	const isAboutRoute = pathname === "/about" || pathname === "/about/";

	return (
		<NavigationMenu className="w-full max-w-[98vw] mx-auto flex justify-between items-center border-b lg:border-none fixed top-0 left-1/2 -translate-x-1/2 z-10 backdrop-blur-md lg:backdrop-blur-none bg-gradient-to-b from-background to-transparent">
			<div className="flex flex-row items-center ">
				<div className="flex flex-row items-center p-3 pr-0 space-x-2">
					<div className="w-5" />

					<DynamicLogo width={35} height={35} />
					<h2 className="flex flex-row gap-1 items-center font-inter text-xl md:text-xl font-bold">
						ChatDKU
						{isDevRoute && (
							// <span className="font-inter text-xs md:text-sm lg:text-sm italic text-primary/20">dev</span>
							<Badge variant="default">Dev</Badge>
						)}
						{!isDevRoute && (
							// <span className="font-inter text-xs md:text-sm lg:text-sm italic text-primary/20">dev</span>
							<Badge variant="default">Student</Badge>
						)}
					</h2>
				</div>
				<TooltipProvider>
					<Tooltip>
						<TooltipTrigger asChild>
							<NavigationMenuLink
								href="/about"
								className={
									isDevRoute
										? "hidden"
										: "lg:text-md flex flex-row items-center"
								}
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
				{/* <NavigationMenuItem> */}
				{/*   <TooltipProvider> */}
				{/*     <Tooltip> */}
				{/*       <TooltipTrigger asChild> */}
				{/*         <NavigationMenuLink */}
				{/*           href={isDevRoute ? "/dev" : "/"} */}
				{/*           className="lg:text-md flex flex-row items-center" */}
				{/*         > */}
				{/*           <p className="hidden sm:block">New Chat</p> */}
				{/*           <SquarePen className="size-5 text-primary-500" /> */}
				{/*         </NavigationMenuLink> */}
				{/*       </TooltipTrigger> */}
				{/*       <TooltipContent className="sm:hidden"> */}
				{/*         <p>New Chat</p> */}
				{/*       </TooltipContent> */}
				{/*     </Tooltip> */}
				{/*   </TooltipProvider> */}
				{/* </NavigationMenuItem> */}
				<NavigationMenuItem>
					<NavigationMenuLink
						href={isDevRoute ? "/dev" : "/"}
						className={
							"bg-secondary rounded-full px-2 " +
							(isAboutRoute ? "block" : "hidden")
						}
					>
						Back to ChatDKU
					</NavigationMenuLink>
				</NavigationMenuItem>
				<NavigationMenuItem>
					<ModeToggle />
				</NavigationMenuItem>
			</NavigationMenuList>
		</NavigationMenu>
	);
}
