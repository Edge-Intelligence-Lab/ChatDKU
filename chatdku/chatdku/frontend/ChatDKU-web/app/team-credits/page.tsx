"use client";

import { useState } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import Link from "next/link";

type MemberProps = {
  name: string;
  classYear: string;
  team: string;
  role: string;
  avatar?: string;
  showContribution?: boolean; 
};

function MajorMember({
  name,
  classYear,
  team,
  role,
  avatar = "/avatars/default.jpg",
  showContribution = true,
}: MemberProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`flex items-start gap-4 p-4 border rounded-xl w-full max-w-5xl mx-auto`}
    >
      {/* Avatar */}
      <Image
        src={avatar}
        alt={name}
        width={64}
        height={64}
        className="rounded-full object-cover"
      />

      {/* Info */}
      <div className="flex-1">
        <p className="font-semibold">
          {name} · {classYear}
        </p>
        <p className="text-sm text-muted-foreground">{team}</p>
    

        {/* Contribution */}
        {showContribution && (
          <div className="mt-2 text-sm">
            <p
                className={expanded ? "whitespace-pre-line" : "line-clamp-2 whitespace-pre-line"}
            >
              {role}
            </p>


            <Button
              variant="link"
              className="px-0 text-sm"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Show less" : "Show more"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function GridMember({
  name,
  classYear,
  avatar = "/avatars/default.png",
  team,
}: {
  name: string;
  classYear: string;
  avatar?: string;
  team?: string; 
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <Image
        src={avatar}
        alt={name}
        width={72}
        height={72}
        className="rounded-full object-cover"
      />
      <p className="text-sm font-medium text-center">{name}</p>
      <p className="text-xs text-muted-foreground">{classYear}</p>
      {team && (
        <p className="text-xs text-muted-foreground text-center">{team}</p>
        )}
    </div>
  );
}

export default function TeamCreditsPage() {
  return (
    <div className="flex justify-center py-10">
      <div className="w-10/12 max-w-4xl space-y-10">
        {/* Back Button */}
        <div className="flex justify-end">
          <Link href="/about">
            <Button variant="outline">← Back to About</Button>
          </Link>
        </div>

        <div className="flex items-center justify-center gap-4 mb-6">

            <Image
                src="/logos/new_logo.svg"
                alt="ChatDKU Logo"
                width={60}
                height={60}
                className="object-contain"
            />
            <h1 className="text-3xl font-bold">
                Credits
            </h1>
        </div>


        {/* Core Members */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Core Members</h2>

          <MajorMember
            name="Bing Luo"
            classYear="PhD"
            team="Project Advisor"
            avatar="/avatars/Bing.jpg"
            role=""
            showContribution={false}
          />

          <MajorMember
            name="Mingxi Li"
            classYear="Research Assistant"
            team="Project Leader"
            avatar="/avatars/Mingxi.jpg"
            role=""
            showContribution={false}
          />

          <MajorMember
            name="Anar Nyambayar"
            classYear="Class of 2027"
            team="Co-developer · Frontend Team Captian / Databases Team member / Agent Team Member"
            avatar="/avatars/Anar.jpg"
            role={`- Lead engineer for the Next.JS web frontend, responsible for interface design and continuous integration.
                - Designed the SQL agent and the accompanying PostgreSQL database schema.
                - Developed a local document ingestion solution to extract structured information from text, PDF, and DOCX documents for relational database population.
                - Implemented adaptive response personalization based on inferred user preferences and interaction context.
                - Added a developer-only mode for testing different agents and features.
                - Migrated the web application to HTTPS.
                - Performed various bug fixes and optimizations.
                `}

          />

          <MajorMember
            name="Munish Lohani"
            classYear="Class of 2028"
            team="Co-developer · Backend Team Captian / Evaluation Team Captian / Agent Team Member"
            avatar="/avatars/Munish.jpg"
            role={`- Managed backend deployment, including the transition from Flask backend to Django with NetID-based authentication, unified PostgreSQL database and implemented task automation using Celery.
                - Developed and integrated speech-to-text functionality for frontend and backend.
                - Working on evaluation.
                `}
          />

          <MajorMember
            name="Temuulen Enkhtamir"
            classYear="Class of 2027"
            team="Co-developer · Evaluation Team Member / Databases Team Member / Agent Team Member"
            avatar="/avatars/Temuulen.jpg"
            role={`- Developed core agent logic and algorithms.
                - Scaled and optimized the database.
                - Updated and enhanced the document ingestion pipeline.
                - Integrated a tool-calling mechanism into the agent system.
                `}
          />

          <MajorMember
            name="Sean Allen Siegfreid R. Bugarin"
            classYear="Class of 2026"
            team="Co-developer"
            avatar="/avatars/Sean.jpg"
            role={`- Conducted he evaluation of ChatDKU, focusing on testing the current large language model and developing standardized datasets to ensure consistent and reliable performance assessment.
                `}
          />

          <MajorMember
            name="Zhiwei Li"
            classYear="Class of 2028"
            team="Co-developer · Databases Team Captain / Agent Team Member"
            avatar="/avatars/Zhiwei.jpg"
            role={`- Implemented database monitoring and performance diagnostics to ensure system stability and enable iterative optimization.
                - Optimized data ingestion, filtering, and storage pipelines to improve reliability and stability of the ChatDKU database.
                - Enhanced agent intelligence by investigating and integrating new features and retrieval mechanisms.
                `}
          />
        </section>

        {/* Alumni */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Alumni</h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <GridMember name="Yuxiang Lin" classYear="Class of 2026" avatar="/avatars/Yuxiang.jpeg"/>
            <GridMember name="Chenshuhao(Cody)Qin" classYear="Class of 2025" avatar="/avatars/Chenshuhao.jpg"/>
            <GridMember name="Ningyuan Yang" classYear="Class of 2026" avatar="/avatars/Ningyuan.jpg"/>
          </div>
        </section>

        {/* New Members */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">New Members</h2>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-6">
            <GridMember name="Youran Wang" classYear="Class of 2029" team="Backend / Databases / Agent Team Member" avatar="/avatars/Youran.jpg"/>
            <GridMember name="Ruihan Yin" classYear="Class of 2028" team="Frontend / Agent Team Member" avatar="/avatars/RuihanYin.jpg"/>
            <GridMember name="Zeyu Yu" classYear="Class of 2028" avatar="/avatars/Zeyu.jpg"/>
            <GridMember name="Haroon Butt" classYear="Class of 2029" avatar="/avatars/Haroon.jpg"/>
            <GridMember name="Jingxuan Lin" classYear="Class of 2029" team="Backend / Agent Team Member" avatar="/avatars/Jingxuan.jpg"/>
          </div>
        </section>
      </div>
    </div>
  );
}
