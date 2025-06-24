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
import { ChevronsUpDown } from "lucide-react";


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
    chatEndpoint: "https://chatdku.dukekunshan.edu.cn/dev/think/chat",
    label: "Deep Think",
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
    label: "Anar testing",
  },
];

interface ComboBoxResponsiveProps {
  inputValue: string;
  onEndpointChange: (endpoint: string) => void;
}

export function ComboBoxResponsive({ inputValue, onEndpointChange }: ComboBoxResponsiveProps) {
  const [open, setOpen] = React.useState(false);
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [selectedStatus, setSelectedStatus] = React.useState<Branch | null>(
    branches[0]
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
          <Button
            variant="ghost"
            className="transition-colors border border-foreground/10 duration-300 w-auto rounded-4xl py-4.5 justify-start"
          >
            {!inputValue &&
              (selectedStatus ? <>{selectedStatus.label}</> : <>Def</>)}
            <ChevronsUpDown className="opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[150px] p-0" align="center">
          <StatusList setOpen={setOpen} setSelectedStatus={setSelectedStatus} />
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Drawer open={open} onOpenChange={setOpen}>
      <DrawerTrigger asChild>
        <Button
          variant="ghost"
          className="w-auto rounded-4xl border border-foreground/10 transition-colors duration-300 bg-transparent active:bg-foreground/10 py-4.5 justify-start"
        >
          {!inputValue &&
            (selectedStatus ? <>{selectedStatus.label}</> : <>Def</>)}
          {inputValue && <ChevronsUpDown className="text-foreground" />}
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
                  branches.find((priority) => priority.chatEndpoint === value) || null
                );
                setOpen(false);
              }}
            >
              {status.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}
