import EditForm from "./ui";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function getShowNotes(name: string) {
  const res = await fetch(`${API_BASE}/episodes/${encodeURIComponent(name)}/show-notes`, { cache: "no-store" });
  if (!res.ok) return { items: [] };
  return res.json();
}

export default async function EditPage({ params }: { params: { name: string } }) {
  const { name } = params;
  const data = await getShowNotes(name);

  return (
    <main className="container mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Edit Show Notes: {decodeURIComponent(name)}</h1>
      <EditForm name={decodeURIComponent(name)} items={data.items || []} />
    </main>
  );
}
