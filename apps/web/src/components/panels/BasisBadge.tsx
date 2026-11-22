import React from "react";

type Basis = "confirmed" | "reported" | "predicted" | "simulated";

const BASIS_STYLES: Record<Basis, { classes: string; label: string }> = {
  confirmed: {
    classes: "bg-teal-100 text-teal-800 border border-teal-300",
    label: "Confirmed",
  },
  reported: {
    classes: "bg-transparent text-gray-700 border border-gray-400",
    label: "Community report",
  },
  predicted: {
    classes: "bg-transparent text-gray-600 border border-dashed border-gray-400",
    label: "Predicted",
  },
  simulated: {
    classes: "bg-gray-100 text-gray-500 border border-gray-200",
    label: "Demo data",
  },
};

export function BasisBadge({
  verificationStatus,
  isSimulated,
}: {
  verificationStatus: string;
  isSimulated: boolean;
}) {
  const basis: Basis = isSimulated
    ? "simulated"
    : (verificationStatus as Basis) ?? "reported";

  const style = BASIS_STYLES[basis] ?? BASIS_STYLES.reported;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.classes}`}
    >
      {style.label}
    </span>
  );
}
