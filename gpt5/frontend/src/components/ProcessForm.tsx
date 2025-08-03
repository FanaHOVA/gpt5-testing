"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function ProcessForm() {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [speakers, setSpeakers] = useState(2);
  const [transcriptOnly, setTranscriptOnly] = useState(false);
  const [generateExtra, setGenerateExtra] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("Submitting...");

    const body = {
      url,
      name,
      speakers,
      transcript_only: transcriptOnly,
      generate_extra: generateExtra,
    };

    const res = await fetch(`${API_BASE}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setStatus(`Error: ${res.status} ${err.detail || ""}`);
      return;
    }

    const data = await res.json();
    setStatus(`Queued. Task ID: ${data.task_id}`);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 p-4 border rounded-lg">
      <h2 className="text-xl font-semibold">New Processing Job</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-sm">Episode Name</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm">File URL</span>
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." required />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm">Speakers</span>
          <Input
            type="number"
            min={1}
            value={speakers}
            onChange={(e) => setSpeakers(parseInt(e.target.value || "0", 10))}
          />
        </label>
      </div>
      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2">
          <Checkbox
            checked={transcriptOnly}
            onCheckedChange={(v) => setTranscriptOnly(Boolean(v))}
          />
          <span>Transcript only</span>
        </label>
        <label className="flex items-center gap-2">
          <Checkbox
            checked={generateExtra}
            onCheckedChange={(v) => setGenerateExtra(Boolean(v))}
          />
          <span>Generate extra (titles, tweets)</span>
        </label>
      </div>
      <Button type="submit">Submit</Button>
      {status && <p className="text-sm text-muted-foreground">{status}</p>}
    </form>
  );
}
