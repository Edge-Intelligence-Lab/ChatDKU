"use client";

import React from "react";
import DynamicLogo from "./dynamic-logo";
import { useState } from "react";
import Remark from "./chatdku_remark";
import Terms from "./ui/terms";
import Modal from "./ui/aboutModel"

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
      <div className="flex flex-col items-center p-4 mt-32 w-4/5 md:max-w-1/2 sm:max-w-4/5  selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
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
      <Modal
      isOpen={termsAndCondition}
      onClose={()=>setTermsAndCondition(false)}
      title="Terms & Conditions"
      >
        <Terms/>

      </Modal>

      <Modal
      isOpen={remarks}
      onClose={()=>setRemarks(false)}
      title="About ChatDKU"
      >
        <Remark/>

      </Modal>
      
    </>
  );
};

export default About;
