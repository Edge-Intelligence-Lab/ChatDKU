"use client";

import React from "react";
import DynamicLogo from "./dynamic-logo";
import { useState } from "react";
import Remark from "./chatdku_remark";
import Terms from "./ui/terms";
import Modal from "./ui/aboutModel";
import Link from "next/link";

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
      <div className="flex flex-col items-center p-2 mt-16 w-10/12 md:max-w-3xl selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
        <div className="mt-12">
          <DynamicLogo height={64} width={64} />
        </div>

        <h1 className="mt-4 lg:mt-8 font-bold text-xl lg:text-2xl">
          About ChatDKU-Advising
        </h1>

        <ol className="list-decimal mt-6 space-y-2 pl-5">
          <li className="text-sm lg:text-md font-medium">
            ChatDKU -{" "}
            <Link
              className="text-blue-500"
              href={"https://chatdku.dukekunshan.edu.cn"}
            >
              https://chatdku.dukekunshan.edu.cn
            </Link>
            , Duke Kunshan University’s dedicated AI chatbot, designed to
            streamline access to campus information and enhance engagement for
            students, faculty, and staff. ChatDKU provides instant, reliable
            answers to DKU-specific queries—saving time and simplifying
            university life. The unique feature of ChatDKU is its local
            deployment to ensure data privacy and security.
          </li>
          <li className="text-sm lg:text-md font-medium">
            We are now releasing ChatDKU 1.0: ChatDKU-Advising, a version
            specifically designed to support academic advising at DKU. It aims
            to assist students by providing quick access to advising-related
            information and guidance, while also helping faculty respond more
            efficiently to common student inquiries.
          </li>
          <li className="text-sm lg:text-md font-medium">
            ChatDKU- Advising is not meant to be a replacement for meeting with
            your advisor or reaching out to the relevant offices when you need
            support. It is a tool to give quick, accurate answers about DKU
            policies but it is important for users to follow up with the
            university personnel involved if you are going to be taking some
            sort of action based on policy.
          </li>
          <li className="text-sm lg:text-md font-medium">
            To improve answer accuracy, please ensure your questions contain
            specific and detailed keywords. This helps avoid misunderstandings
            or incorrect interpretations.
          </li>
        </ol>

        <p className="text-center text-sm mt-4 lg:mt-8 text-muted-foreground">
          Developed by DKU Edge Intelligence Lab, in partnership with the IGHE
          SET Lab and Office of Undergraduate Advising.
        </p>

        <div className="links flex gap-3 text-sm">
          <span
            className="text-blue-500 active:text-blue-400 cursor-pointer c"
            onClick={handleTermsAndCondition}
          >
            <h3>Terms & Conditions</h3>
          </span>
          <span
            className="text-blue-500 active:text-blue-400 cursor-pointer c"
            onClick={handleRemarks}
          >
            <h3>Learn More</h3>
          </span>
        </div>
        <Modal
          isOpen={termsAndCondition}
          onClose={() => setTermsAndCondition(false)}
          title="Terms & Conditions"
        >
          <Terms />
        </Modal>

        <Modal
          isOpen={remarks}
          onClose={() => setRemarks(false)}
          title="About ChatDKU"
        >
          <Remark />
        </Modal>
      </div>
    </>
  );
};

export default About;
