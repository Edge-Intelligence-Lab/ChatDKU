import React from "react";
import Image from "next/image";
import Link from "next/link";

const Starter: React.FC = () => {
  return (
    <div className="flex flex-col items-center pt-32 md:max-w-1/2 sm:max-w-4/5">
      {/* Logo */}
      <div>
        <Image
          src="/logos/Light-Logo.png"
          alt="Logo"
          className="w-12 h-12"
          width={96}
          height={96}
        />
      </div>

      <h1 className="pt-4 font-bold text-2xl">About ChatDKU-Advising</h1>

      <ul className="list-none mt-6 space-y-2">
        <li className="text-md font-medium list-decimal">ChatDKU-Advising only provides answers based on official and publicly available information from Duke Kunshan University, including resources from the Student Bulletin, Academic Advising Office, and Faculty Directory Websites.</li>
        <li className="text-md font-medium list-decimal">To improve answer accuracy, please ensure your questions contain specific and detailed keywords. This helps avoid misunderstandings or incorrect interpretations.</li>
      </ul>

      <p className="text-sm pt-8"><Link className=" text-blue-500" href="https://chatdku.dukekunshan.edu.cn/terms.html">Terms & Conditions</Link> and <Link className="text-blue-500" href={"https://chatdku.dukekunshan.edu.cn/chatdku_remarks.html"}>more information</Link>.</p>

      <div className="flex justify-around mt-8 space-x-6">
        <div className="flex flex-col items-center w-60 p-4 border border-primary/10 rounded-lg shadow-lg shadow-primary/5">
          <div className="text-4xl mb-2">🔍</div>
          <p className="text-center text-sm font-medium">Academic and Course Inquiries</p>
        </div>
        <div className="flex flex-col items-center w-60 p-4 border border-primary/10 rounded-lg shadow-lg shadow-primary/5">
            <div className="text-4xl mb-2">🎓</div>
          <p className="text-center text-sm font-medium">Major and Career Development</p>
        </div>
        <div className="flex flex-col items-center w-60 p-4 border border-primary/10 rounded-lg shadow-lg shadow-primary/5">
          <div className="text-4xl mb-2">⚙️</div>
          <p className="text-center text-sm font-medium">Academic Guidelines and Policies</p>
        </div>
      </div>
    </div>
  );
};

export default Starter;
