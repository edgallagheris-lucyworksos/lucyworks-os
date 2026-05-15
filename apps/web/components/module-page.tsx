"use client";
import { useEffect, useState } from "react";
import { API_BASE_DEFAULT } from "@lucyworks/shared";

export function ModulePage({ title, endpoint }: { title: string; endpoint: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE || API_BASE_DEFAULT}${endpoint}`)
      .then((r) => r.json())
      .then(setData)
      .catch(async () => {
        const fallback = await fetch("/seed/hospital_snapshot.json").then((r) => r.json());
        setData(fallback);
      });
  }, [endpoint]);
  return <main style={{padding:16}}><h1>{title}</h1><pre>{JSON.stringify(data, null, 2)}</pre></main>;
}
