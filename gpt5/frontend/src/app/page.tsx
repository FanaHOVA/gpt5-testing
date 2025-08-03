import Link from "next/link";
import ProcessForm from "@/components/ProcessForm";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Episode = {
  name: string;
  created_at: string;
  created_at_formatted: string;
};

async function getEpisodes(): Promise<Episode[]> {
  const res = await fetch(`${API_BASE}/episodes`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export default async function Home() {
  const episodes = await getEpisodes();

  return (
    <main className="container mx-auto p-6 space-y-8">
      <h1 className="text-3xl font-bold">Smol Podcaster</h1>
      <ProcessForm />

      <section>
        <h2 className="text-xl font-semibold mb-3">Episodes</h2>
        <div className="overflow-x-auto rounded border">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Created</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {episodes.length === 0 && (
                <tr>
                  <td className="px-3 py-3" colSpan={3}>
                    No episodes yet.
                  </td>
                </tr>
              )}
              {episodes.map((ep) => (
                <tr key={ep.name} className="border-t">
                  <td className="px-3 py-2 font-mono">{ep.name}</td>
                  <td className="px-3 py-2">{ep.created_at_formatted}</td>
                  <td className="px-3 py-2">
                    <Link
                      className="rounded bg-gray-900 text-white px-3 py-1 text-xs"
                      href={`/edit/${encodeURIComponent(ep.name)}`}
                    >
                      Edit Show Notes
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
