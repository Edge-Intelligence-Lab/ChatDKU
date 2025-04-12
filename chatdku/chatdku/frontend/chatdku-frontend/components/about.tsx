import React from "react";
import Link from "next/link";
import DynamicLogo from "./ui/dynamic-logo";

const About: React.FC = () => {
  return (
    <div className="flex flex-col items-center p-4 mt-32 w-4/5 md:max-w-1/2 sm:max-w-4/5">
      <DynamicLogo height={64} width={64} />

      <h1 className="mt-4 lg:mt-8 font-bold text-xl lg:text-2xl">About ChatDKU-Advising</h1>

      <ul className="list-none mt-6 space-y-2">
        <li className="text-sm lg:text-md font-medium list-decimal">ChatDKU-Advising only provides answers based on official and publicly available information from Duke Kunshan University, including resources from the Student Bulletin, Academic Advising Office, and Faculty Directory Websites.</li>
        <li className="text-sm lg:text-md font-medium list-decimal">To improve answer accuracy, please ensure your questions contain specific and detailed keywords. This helps avoid misunderstandings or incorrect interpretations.</li>
      </ul>

      <p className="text-center text-sm mt-4 lg:mt-8 text-muted-foreground">
        Developed by DKU Edge Intelligence Lab.
      </p>

      <p className="text-xs pt-8"><Link className=" text-blue-500" href="https://chatdku.dukekunshan.edu.cn/terms.html">Terms & Conditions</Link> and <Link className="text-blue-500" href={"https://chatdku.dukekunshan.edu.cn/chatdku_remarks.html"}>more information</Link>.</p>

    </div>
  );
};

export default About;