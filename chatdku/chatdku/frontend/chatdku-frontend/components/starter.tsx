import React from "react";
import Image from "next/image";

const Starter: React.FC = () => {
  return (
    <div className="flex flex-col items-center pt-6 md:max-w-1/2 sm:max-w-4/5">
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

      {/* List */}
      <ul className="list-none mt-6 space-y-2">
        <li className="text-md font-medium list-decimal">ChatDKU-Advising only provides answers based on official and publicly available information from Duke Kunshan University, including resources of Student Bulletin, Academic Advising Office Information, Faculty Directory Websites.</li>
        <li className="text-md font-medium list-decimal">To improve answer accuracy, please ensure your questions contain specific and detailed keywords. This helps avoid misunderstandings or incorrect interpretations.</li>
      </ul>

      <p className="text-sm pt-8">Terms & Conditions and more information.</p>

      {/* Cards */}
      <div className="flex justify-around mt-8 space-x-4">
        {/* Card 1 */}
        <div className="flex flex-col items-center w-40 p-4 border border-gray-300 rounded-lg shadow-sm">
          <div className="text-4xl mb-2">🔍</div>
          <p className="text-center text-sm font-medium">Academic and Course Inquiries</p>
        </div>

        {/* Card 2 */}
        <div className="flex flex-col items-center w-40 p-4 border border-gray-300 rounded-lg shadow-sm">
            <div className="text-4xl mb-2">🎓</div>
          <p className="text-center text-sm font-medium">Major and Career Development</p>
        </div>

        {/* Card 3 */}
        <div className="flex flex-col items-center w-40 p-4 border border-gray-300 rounded-lg shadow-sm">
          <div className="text-4xl mb-2">⚙️</div>
          <p className="text-center text-sm font-medium">Academic Guidelines and Policies</p>
        </div>
      </div>
    </div>
  );
};

export default Starter;
