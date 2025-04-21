import { X } from "lucide-react";


interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
  }
  
  const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => (
    <div
      className={`absolute t-0 w-full h-[calc(90vh-90px)] overflow-auto bg-white dark:bg-background backdrop-blur-md flex justify-center items-center transition-all duration-300 transform ${
        isOpen
          ? "translate-y-0 opacity-100 scale-100"
          : "pointer-events-none translate-y-6 opacity-0 scale-95"
      }`}
    >
      <div className={`container relative z-20 w-[80vw] md:w-[70vw] h-[75vh] p-3 bg-zinc-100/60 dark:bg-muted/50 rounded-2xl shadow-lg`}>
        <button
          className="absolute right-4 cursor-pointer z-50 w-4 h-4"
          onClick={onClose}
          aria-label="Close modal"
        >
          <X />
        </button>
        <div className="overflow-auto h-[90%] flex flex-col">
          <div className="sticky top-0 z-10 pb-2">
            <h2 className="text-center text-xl ls:text-2xl font-bold mb-2">
              {title}
            </h2>
          </div>
          <div className="flex-1 overflow-auto pr-2">
            {children}
          </div>
        </div>
      </div>
    </div>
  );

  export default Modal