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

type Status = {
  value: string;
  label: string;
};

const statuses: Status[] = [
  {
    value: "standard",
    label: "Standard",
  },
  {
    value: "deepThink",
    label: "Deep Think",
  },
  {
    value: "qwen",
    label: "Qwen",
  },
  {
    value: "9030",
    label: "Temuulen",
  },
];

interface ComboBoxResponsiveProps {
  inputValue: string;
}

export function ComboBoxResponsive({ inputValue }: ComboBoxResponsiveProps) {
  const [open, setOpen] = React.useState(false);
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [selectedStatus, setSelectedStatus] = React.useState<Status | null>(
    statuses[0] // Set "Standard" as default option
  );

  if (isDesktop) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className="w-auto rounded-4xl py-4.5 gap-0 justify-start"
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
          variant="outline"
          className="w-auto rounded-4xl transition-colors duration-300 active:bg-foreground/10 py-4.5 justify-start"
        >
          {!inputValue &&
            (selectedStatus ? <>{selectedStatus.label}</> : <>Def</>)}
          {inputValue && <ChevronsUpDown className="opacity-50" />}
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
  setSelectedStatus: (status: Status | null) => void;
}) {
  return (
    <Command>
      {/* <CommandInput placeholder="Filter status..." /> */}
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup>
          {statuses.map((status) => (
            <CommandItem
              key={status.value}
              value={status.value}
              onSelect={(value) => {
                setSelectedStatus(
                  statuses.find((priority) => priority.value === value) || null
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
