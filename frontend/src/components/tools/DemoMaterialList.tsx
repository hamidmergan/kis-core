import Checkbox from "@/components/ui/Checkbox";
import Select from "@/components/ui/Select";

/** The fixed material of a demo: the workspace and its files, shown but not changeable. */
export default function DemoMaterialList({ selectId, workspace, files, sourcesLabel, note }: {
  selectId: string;
  workspace: string;
  files: string[];
  sourcesLabel: string;
  note: string;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label htmlFor={selectId} className="block text-sm font-medium text-foreground-soft mb-2">
          Workspace
        </label>
        <Select id={selectId} value="demo" onChange={() => {}} disabled
          options={[{ value: "demo", label: workspace }]} />
      </div>
      <div>
        <span className="block text-sm font-medium text-foreground-soft mb-2">{sourcesLabel}</span>
        <ul className="space-y-2">
          {files.map((name) => (
            <li key={name}>
              <Checkbox checked disabled onChange={() => {}} label={name} labelClassName="text-sm text-foreground" />
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted">{note}</p>
      </div>
    </div>
  );
}
