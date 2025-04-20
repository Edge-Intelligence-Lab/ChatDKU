"use client";

import React from "react";
import DynamicLogo from "./dynamic-logo";
import { useState } from "react";
import { X } from "lucide-react";
import Remark from "./chatdku_remark";
import Terms from "./ui/terms";

const About: React.FC = () => {
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
      <div className="flex flex-col items-center p-4 mt-32 w-4/5 md:max-w-1/2 sm:max-w-4/5">
        <DynamicLogo height={64} width={64} />

        <h1 className="mt-4 lg:mt-8 font-bold text-xl lg:text-2xl">
          About ChatDKU-Advising
        </h1>

        <ul className="list-none mt-6 space-y-2">
          <li className="text-sm lg:text-md font-medium list-decimal">
            ChatDKU-Advising only provides answers based on official and
            publicly available information from Duke Kunshan University,
            including resources from the Student Bulletin, Academic Advising
            Office, and Faculty Directory Websites.
          </li>
          <li className="text-sm lg:text-md font-medium list-decimal">
            To improve answer accuracy, please ensure your questions contain
            specific and detailed keywords. This helps avoid misunderstandings
            or incorrect interpretations.
          </li>
        </ul>

        <p className="text-center text-sm mt-4 lg:mt-8 text-muted-foreground">
          Developed by DKU Edge Intelligence Lab.
        </p>

        <div className="links flex gap-3 text-sm">
          <span
            className="text-blue-700 active:text-blue-500 cursor-pointer c"
            onClick={handleTermsAndCondition}
          >
            <h3>Terms & Condition</h3>
          </span>
          <span
            className="text-blue-700 active:text-blue-500 cursor-pointer c"
            onClick={handleRemarks}
          >
            <h3>Learn More</h3>
          </span>
        </div>
      </div>
      <div
        className={`T&C   absolute t-0 w-[100%] h-[calc(90vh-90px)] overflow-auto bg-white my-3 dark:bg-background backdrop-blur-md  flex justify-center align-center items-center transition-all duration-300 transform ${
          termsAndCondition
            ? "translate-y-0 opacity-100 scale-100"
            : "pointer-events-none translate-y-4 opacity-0 scale-90"
        }`}
      >
        <div
          className={`container relative z-20 w-[80vw] md:w-[70vw] h-[75vh] p-3 bg-zinc-100 dark:bg-muted/50 rounded-2xl backdrop-blur-2xl transition-all duration-300 transform ${
            termsAndCondition
              ? "translate-y-0 opacity-100 scale-100"
              : "pointer-events-none translate-y-6 opacity-0 scale-95"
          }`}
        >
          <div
            className="cross absolute right-4 cursor-pointer z-50 w-4 h-4"
            onClick={() => {
              setTermsAndCondition(false);
            }}
          >
            <X />
          </div>
          <div className="overflow-auto h-[90%] flex flex-col">
            <div className="sticky top-0 z-10 pb-2 ">
              <h2 className="text-center text-xl ls:text-2xl font-bold mb-2">
                Terms & Conditions
              </h2>
            </div>
            <div className="flex-1 overflow-auto pr-2 ">
              <Terms />
            </div>
          </div>
        </div>
      </div>
      <div
        className={`LM  absolute t-0 w-[100%] h-[calc(90vh-90px)] overflow-auto bg-white dark:bg-background backdrop-blur-md  flex justify-center align-center items-center transition-all duration-300 transform ${
          remarks
            ? "translate-y-0 opacity-100 scale-100"
            : "pointer-events-none translate-y-6 opacity-0 scale-95"
        }`}
      >
        <div
          className={`container relative z-20 w-[80vw] md:w-[70vw] h-[75vh] p-3 bg-zinc-100 dark:bg-muted/50 rounded-2xl backdrop-blur-2xl transition-all duration-300 transform ${
            remarks
              ? "translate-y-0 opacity-100 scale-100"
              : "pointer-events-none translate-y-6 opacity-0 scale-90"
          }`}
        >
          <div
            className="cross absolute right-4 cursor-pointer z-50 w-4 h-4"
            onClick={() => {
              setRemarks(false);
            }}
          >
            <X />
          </div>
          <div className="overflow-auto h-full flex flex-col">
            <div className="sticky top-0 z-10 pb-2 ">
              <h2 className="text-center text-xl ls:text-2xl font-bold mb-2 my-3">
              Some Remarks on ChatDKU for a General Audience
              </h2>
            </div>
            <div className="flex-1 overflow-auto pr-2 ">
              <Remark />
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default About;
