import React from "react";
import { Circle } from "lucide-react";

interface Props {
  lastCheckMins?: number;
  isScanning?: boolean;
}

export function StatusLine({ lastCheckMins = 0, isScanning = false }: Props) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted select-none">
      {/* Static dot — not animated */}
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          isScanning ? "bg-yellow-400" : "bg-green-500"
        }`}
      />
      <span>
        {isScanning
          ? "Scanning..."
          : `Monitoring · last check ${lastCheckMins === 0 ? "just now" : `${lastCheckMins} min ago`}`}
      </span>
    </div>
  );
}
