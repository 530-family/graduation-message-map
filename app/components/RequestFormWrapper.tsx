"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import RequestForm from "./RequestForm";

function RequestFormInner() {
  const searchParams = useSearchParams();
  const isOpen = searchParams.get("apply") === "true" || searchParams.get("open") === "true";

  // Return a controlled version of RequestForm when opened via URL params
  if (isOpen) {
    return <RequestForm isOpen={true} onOpenChange={() => {}} />;
  }

  return <RequestForm />;
}

export default function RequestFormWrapper() {
  return (
    <Suspense fallback={null}>
      <RequestFormInner />
    </Suspense>
  );
}
