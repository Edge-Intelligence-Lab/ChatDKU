"use client";

import React from "react";
import DynamicLogo from "./dynamic-logo";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { ArrowUpRight } from "lucide-react";
import Image from "next/image";

type AboutProps = {
  showCredits?: boolean;
};

const About: React.FC<AboutProps> = ({ showCredits = true }) => {

	const [termsAndCondition, setTermsAndCondition] = useState(false);
	const [remarks, setRemarks] = useState(false);

	const handleTermsAndCondition = () => {
		setTermsAndCondition(true);
	};

	const handleRemarks = () => {
		setRemarks(true);
	};

	return (
		<>
			<div className="flex flex-col items-center p-2 mt-4 w-10/12 md:max-w-3xl selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
				<div className="flex space-x-2 items-center">
					<div className="mt-4">
						<DynamicLogo height={64} width={64} />
					</div>

					<h1 className="mt-4 font-bold text-2xl">About ChatDKU</h1>
				</div>

				<ol className="list-decimal mt-6 space-y-2 pl-5">
					<li className="text-xs md:text-md">
						ChatDKU, Duke Kunshan University’s dedicated AI chatbot, is designed
						to streamline access to campus information and enhance engagement
						for students, faculty, and staff. ChatDKU provides instant, reliable
						answers to DKU-specific queries—saving time and simplifying
						university life. The unique feature of ChatDKU is its local
						deployment to ensure data privacy and security.
					</li>
					<li className="text-xs md:text-md">
						ChatDKU-Student is not meant to be a replacement for advisor
						meetings or communication with relevant offices when you need
						support. It is a tool to give quick, accurate answers about DKU
						policies but it is important for users to follow up with the
						university personnel involved if you are going to be taking some
						sort of action based on policy.
					</li>
					<li className="text-xs md:text-md">
						All A.I. systems have the potential to make an error for a variety
						of reasons. While the developers of this platform will make every
						effort to make this platform as accurate as possible, it is the
						user’s responsibility to double check the accuracy of any answers
						provided by the system. If a user misses a deadline or neglects to
						take an action because of an answer given by the system, the
						responsibility for that rests on the user, not on ChatDKU.
						Screenshots of responses provided by the system cannot serve as a
						rationale to provide exceptions to policies outlined in the
						Undergraduate Bulletin or deadlines set in the Academic Calendar.
					</li>
					<li className="text-xs md:text-md">
						To improve answer accuracy, please ensure your questions contain
						specific and detailed keywords. This helps avoid misunderstandings
						or incorrect interpretations.
					</li>
				</ol>

				{/* Show different logo based on theme */}
				<span className="block dark:hidden">
					<Image
						src="/logos/BL_Edge Intelligence Lab_04.png"
						alt="Edge Intelligence Lab logo."
						width={300}
						height={50}
						className="mt-2 mb-2"
					/>
				</span>
				<span className="hidden dark:block">
					<Image
						src="/logos/BL_Edge Intelligence Lab_06.png"
						alt="Edge Intelligence Lab logo dark."
						width={300}
						height={50}
						className="mt-2 mb-2"
					/>
				</span>
				<p className="text-center text-sm text-muted-foreground">
					Developed by DKU Edge Intelligence Lab, in partnership with the IGHE
					SET Lab and Office of Undergraduate Advising.
				</p>

				<div className="flex flex-col sm:flex-row items-center space-x-2 mb-4">
					{" "}
					<Dialog>
						<DialogTrigger asChild className="my-4 cursor-pointer">
							<Button variant="outline">View Terms and Conditions</Button>
						</DialogTrigger>
						<DialogContent className="sm:max-w-[500px] max-h-[90vh]">
							<DialogHeader>
								<DialogTitle>Terms and Conditions</DialogTitle>
							</DialogHeader>
							<ScrollArea className="h-[80vh] w-full rounded-md p-2">
								<h2 className="text-xl font-bold">1. Access and Use</h2>
								<ul className="my-3">
									<li>
										<strong>Community Access:</strong> ChatDKU is available to
										all members of the Duke Kunshan University community,
										including students, faculty, staff, and related personnel.
										There is no age restriction, but users must be affiliated
										with DKU.
									</li>
									<li>
										<strong>Account Responsibility:</strong> Users are
										responsible for maintaining the confidentiality of their
										account credentials and for all activities conducted through
										their accounts. Unauthorized account use should be reported
										immediately.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">2. Usage Guidelines</h2>
								<ul className="my-3">
									<li>
										<strong>Purpose of Use:</strong> ChatDKU is intended to
										facilitate access to DKU-related information and support
										academic and administrative activities. Users are encouraged
										to use ChatDKU for educational, research, and community
										interaction purposes.
									</li>
									<li>
										<strong>Prohibited Conduct:</strong> Users must not use
										ChatDKU for any illegal activities, infringe on the rights
										of others, or disseminate harmful or inappropriate content.
										This includes, but is not limited to, harassment,
										discrimination, and the spread of false information.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									3. Privacy and Data Protection
								</h2>
								<ul className="my-3">
									<li>
										<strong>Data Processing:</strong> ChatDKU collects and
										processes user interaction information, including
										conversation history and user identity, to improve service
										quality. Data will be anonymized where possible to protect
										user privacy. Your questions and the answers received may be
										used to train ChatDKU to improve its performance, but your
										private data will be specially processed and not associated
										with your account, ensuring no one knows who asked the
										question.
									</li>
									<li>
										<strong>Data Storage and Access:</strong> Conversation
										history may be stored on secure servers to maintain
										continuity across sessions and devices. Access to stored
										data is limited to authorized personnel and is used solely
										for service improvement and research.
									</li>
									<li>
										<strong>User Authentication:</strong> The Duke Shibboleth
										system has been integrated to ensure secure user
										authentication, ensuring that sensitive information is
										accessible only to authorized users.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									4. Content Management
								</h2>
								<ul className="my-3">
									<li>
										<strong>User Contributions:</strong> Users retain ownership
										of the content they input into ChatDKU. By using the
										service, users grant ChatDKU permission to use, copy, and
										distribute this content to provide and improve the service.
									</li>
									<li>
										<strong>Content Accuracy:</strong> While ChatDKU strives to
										provide accurate and reliable information, users should
										independently verify critical information and report any
										inaccuracies to the development team.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									5. Security and Confidentiality
								</h2>
								<ul className="my-3">
									<li>
										<strong>Security Measures:</strong> ChatDKU employs strict
										security protocols to protect user data from unauthorized
										access and disclosure. Users should report any security
										vulnerabilities or incidents.
									</li>
									<li>
										<strong>Confidential Information:</strong> Users must not
										disclose confidential or proprietary information through
										ChatDKU. The platform is not suitable for handling sensitive
										personal or institutional data without appropriate
										safeguards.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									6. Permissions and Access Control
								</h2>
								<ul className="my-3">
									<li>
										<strong>Role-Based Access:</strong> Access to specific
										datasets and features within ChatDKU is managed by user
										roles (e.g., students, faculty, staff). This ensures that
										users receive appropriate resource access based on their
										affiliation with DKU.
									</li>
									<li>
										<strong>Tool Usage:</strong> The use of tools within ChatDKU
										is governed by a permissions system to prevent unauthorized
										actions and ensure compliance with university policies.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									7. AI Safety and Limitations
								</h2>
								<ul className="my-3">
									<li>
										<strong>Hallucinations and Errors:</strong> As an AI-driven
										platform, ChatDKU may occasionally produce incorrect or
										misleading outputs. Users should maintain critical judgment
										and report any issues to improve system accuracy.
									</li>
									<li>
										<strong>Safety Protocols:</strong> ChatDKU integrates safety
										mechanisms to minimize harmful outputs. Users should
										promptly report any unsafe or inappropriate content.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">
									8. Development and Scalability
								</h2>
								<ul className="my-3">
									<li>
										<strong>Continuous Improvement:</strong> ChatDKU
										continuously evolves based on user feedback and
										technological advancements. Users are invited to contribute
										to the platform's development through suggestions for
										improvements and additional resources.
									</li>
									<li>
										<strong>Integration of New Features:</strong> Future updates
										may include support for more complex reasoning and
										relational data integration to better meet the needs of the
										DKU community.
									</li>
								</ul>
								<h2 className="text-xl font-bold m-0.5">9. General Terms</h2>
								<ul className="my-3">
									<li>
										<strong>Revisions:</strong> These terms of use may be
										updated periodically to reflect changes in technology, law,
										or university policies. Users will be notified of
										significant changes, and continued use of ChatDKU
										constitutes acceptance of the updated terms.
									</li>
									<li>
										<strong>Applicable Law:</strong> These terms are governed by
										the applicable laws of Duke Kunshan University. Any disputes
										arising from these terms will be resolved in accordance with
										university procedures.
									</li>
								</ul>
								<p className="font-bold">
									Thank you for using ChatDKU to enhance your academic and
									community experience at Duke Kunshan University. Your
									participation and feedback are vital to us.
								</p>
							</ScrollArea>
							{/* <DialogFooter>
              <Button type="submit">Accept</Button>
            </DialogFooter> */}
						</DialogContent>
					</Dialog>
					<Link href="/ChatDKU-1.0_Introduction.pdf">
						<Button variant={"outline"} className=" flex flex-row items-center">
							Get the Guidebook
							<ArrowUpRight />
						</Button>
					</Link>

					{showCredits && (
  						<Link href="/team-credits">
   							<Button variant="outline" className="flex flex-row items-center">
    							Credits
  						 	 	<ArrowUpRight />
  							</Button>
 						</Link>
					)}


				</div>
			</div>
		</>
	);
};

export default About;