import { useSession } from "../App";
import { ImportPanel } from "../components/ImportPanel";
import { PageHeader } from "../components/ui";

export default function ImportPage() {
  const { local } = useSession();
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Import a video" subtitle="Videos stay on your computer. Nothing is uploaded to the internet." />
      <ImportPanel isLocal={local} />
    </div>
  );
}
