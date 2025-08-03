"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Item = { text: string; url?: string | null };

export default function EditForm({ name, items }: { name: string; items: Item[] }) {
  const [list, setList] = useState<Item[]>(items);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  function update(idx: number, field: keyof Item, value: string) {
    setList((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  }
  function add() {
    setList((prev) => [...prev, { text: "" }]);
  }
  function remove(idx: number) {
    setList((prev) => prev.filter((_, i) => i !== idx));
  }

  async function save() {
    setSaving(true);
    setStatus(null);
    const body = { items: list.map((i) => ({ text: i.text, url: i.url || null })) };
    const res = await fetch(`${API_BASE}/episodes/${encodeURIComponent(name)}/show-notes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setSaving(false);
    setStatus(res.ok ? "Saved" : `Error: ${res.status}`);
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Button onClick={add} variant="outline" className="text-sm">Add item</Button>
        <Button onClick={save} disabled={saving} className="text-sm">
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
      <ul className="space-y-3">
        {list.map((it, idx) => (
          <li key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
            <Input
              className="md:col-span-5"
              placeholder="Text"
              value={it.text}
              onChange={(e) => update(idx, "text", e.target.value)}
            />
            <Input
              className="md:col-span-5"
              placeholder="URL (optional)"
              value={it.url || ""}
              onChange={(e) => update(idx, "url", e.target.value)}
            />
            <Button onClick={() => remove(idx)} variant="destructive" className="md:col-span-2">
              Remove
            </Button>
          </li>
        ))}
      </ul>
      {status && <p className="text-sm text-muted-foreground">{status}</p>}
    </div>
  );
}
