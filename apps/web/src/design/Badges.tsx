import type { Basis, Kind, Severity } from "../api/types";

export const KIND_LABEL: Record<Kind, string> = {
  pothole: "Pothole", road_damage: "Road damage", closure: "Road closure", construction: "Construction", other: "Other",
};
const BASIS_LABEL: Record<Basis, string> = { confirmed: "Confirmed", reported: "Reported", predicted: "Predicted" };

export const SeverityBadge = ({ s }: { s: Severity }) => <span className="sev" data-s={s}>{s[0].toUpperCase() + s.slice(1)}</span>;
export const BasisBadge = ({ b }: { b: Basis }) => <span className="basis" data-b={b}>{BASIS_LABEL[b]}</span>;
export const DemoTag = () => <span className="demo">Demo data</span>;
export const CategoryChip = ({ kind }: { kind: Kind }) => <span className="cat">{KIND_LABEL[kind]}</span>;
