import About from "@/components/about";
import { Navbar } from "@/components/navbar";

export default function AboutPage() {
	return (
		<div>
			<Navbar />
			<div className="flex flex-col items-center mt-16">
				<About />
			</div>
		</div>
	);
}
