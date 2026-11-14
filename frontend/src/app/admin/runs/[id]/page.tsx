"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";

import { RunReview } from "../runs-client";

function RunReviewRoute() {
  const params = useParams<{ id: string }>();
  return <RunReview runId={params.id} />;
}

export default function RunPage() {
  return (
    <Suspense fallback={<p className="p-10 text-zinc-500">Loading run review...</p>}>
      <RunReviewRoute />
    </Suspense>
  );
}
