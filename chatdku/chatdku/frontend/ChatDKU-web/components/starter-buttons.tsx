import React from "react";
import { Button } from "@/components/ui/button";

const StarterButtons: React.FC = () => {
  return (
    <div className="flex flex-col sm:flex-row justify-around mt-8 gap-4 sm:space-x-6">
      <Button
        variant="outline"
        className="flex flex-col items-center w-full sm:min-w-[200px] sm:max-w-[200px] p-4 hover:bg-secondary shadow-lg shadow-primary/5 h-[120px]"
      >
        <div className="text-4xl mb-2">🔍</div>
        <p className="text-center text-sm font-medium whitespace-normal">Academic and Course Inquiries</p>
      </Button>
      
      <Button
        variant="outline"
        className="flex flex-col items-center w-full sm:min-w-[200px] sm:max-w-[200px] p-4 hover:bg-secondary shadow-lg shadow-primary/5 h-[120px]"
      >
        <div className="text-4xl mb-2">🎓</div>
        <p className="text-center text-sm font-medium whitespace-normal">Major and Career Development</p>
      </Button>
      
      <Button
        variant="outline"
        className="flex flex-col items-center w-full sm:min-w-[200px] sm:max-w-[200px] p-4 hover:bg-secondary shadow-lg shadow-primary/5 h-[120px]"
      >
        <div className="text-4xl mb-2">⚙️</div>
        <p className="text-center text-sm font-medium whitespace-normal">Academic Guidelines and Policies</p>
      </Button>
    </div>
  );
};

export default StarterButtons; 