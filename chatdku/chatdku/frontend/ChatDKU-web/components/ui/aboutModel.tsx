import { X } from "lucide-react";


interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
  }
  
  const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => (
    <div
      className={`absolute t-0 w-full h-[90vh] overflow-auto flex justify-center items-center transition-all transform selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black ${
        isOpen
          ? "translate-y-0 opacity-100 scale-100"
          : "pointer-events-none translate-y-6 opacity-0 scale-95"
      }`}
    >
      <div className={`container relative z-20 mt-2 w-[80vw] md:w-[70vw] h-[80vh] p-3 bg-secondary/80 backdrop-blur-2xl rounded-2xl shadow-lg`}>
        <button
          className="absolute right-4 cursor-pointer z-50 w-4 h-4"
          onClick={onClose}
          aria-label="Close modal"
        >
          <X />
        </button>
        <div className="overflow-auto h-full flex flex-col animate-in fade-in-5">
          <div className="sticky top-0 z-10">
            <h2 className="text-center text-xl ls:text-2xl font-bold mb-2">
              {title}
            </h2>
          </div>
          <div className="flex-1 overflow-auto text-xs md:text-sm">
            {children}
          </div>
        </div>
      </div>
    </div>
  );

  export default Modal