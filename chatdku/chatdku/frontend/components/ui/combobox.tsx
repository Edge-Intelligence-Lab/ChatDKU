"use client";

import * as React from "react";

import { useMediaQuery } from "@/components/hooks/use-media-query";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { BrainCircuit, ChevronsUpDown } from "lucide-react";

type Branch = {
  chatEndpoint: string;
  label: string;
};

const branches: Branch[] = [
  {
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/api/chat",
    label: "Standard",
  },
  {
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/dev/qwen/chat",
    label: "Qwen",
  },
  {
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/dev/inp/chat",
    label: "integrated_new_prompt",
  },
  {
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/dev/ant/chat",
    label: "Course Planning",
  },
  {
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/dev/django/chat",
    label: "Django testing",
  },
];

interface ComboBoxResponsiveProps {
  inputValue: string;
  onEndpointChange: (endpoint: string) => void;
}

export function ComboBoxResponsive({
  inputValue,
  onEndpointChange,
}: ComboBoxResponsiveProps) {
  const [open, setOpen] = React.useState(false);
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [selectedStatus, setSelectedStatus] = React.useState<Branch | null>(
    branches[0],
  );

  // Update endpoint when selected status changes
  React.useEffect(() => {
    if (selectedStatus) {
      onEndpointChange(selectedStatus.chatEndpoint);
    }
  }, [selectedStatus, onEndpointChange]);

  if (isDesktop) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant={"inChatbox"} className="w-full justify-start">
            <BrainCircuit />
            {selectedStatus?.label}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[300px] p-0" align="center">
          <StatusList setOpen={setOpen} setSelectedStatus={setSelectedStatus} />
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Drawer open={open} onOpenChange={setOpen}>
      <DrawerTrigger asChild>
        <Button variant={"inChatbox"} className="w-full justify-start">
          {/* <ChevronsUpDown /> */}
          <BrainCircuit className="w-5 h-5" />
          {!inputValue &&
            (selectedStatus ? <>{selectedStatus.label}</> : <>Def</>)}
        </Button>
      </DrawerTrigger>
      <DrawerContent>
        <div className="mt-4 border-t">
          <StatusList setOpen={setOpen} setSelectedStatus={setSelectedStatus} />
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function StatusList({
  setOpen,
  setSelectedStatus,
}: {
  setOpen: (open: boolean) => void;
  setSelectedStatus: (status: Branch | null) => void;
}) {
  return (
    <Command>
      {/* <CommandInput placeholder="Filter status..." /> */}
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup>
          {branches.map((status) => (
            <CommandItem
              key={status.chatEndpoint}
              value={status.chatEndpoint}
              onSelect={(value) => {
                setSelectedStatus(
                  branches.find(
                    (priority) => priority.chatEndpoint === value,
                  ) || null,
                );
                setOpen(false);
              }}
              className="hover:bg-accent active:bg-accent"
            >
              {status.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}
