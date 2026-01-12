"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import RequestForm from "./RequestForm";

function RequestFormInner() {
  const searchParams = useSearchParams();
  const [internalIsOpen, setInternalIsOpen] = useState(false);

  // URL params로 열리도록 초기화
  useEffect(() => {
    if (searchParams.get("apply") === "true" || searchParams.get("open") === "true") {
      setInternalIsOpen(true);
    }
  }, [searchParams]);

  return <RequestForm isOpen={internalIsOpen} onOpenChange={setInternalIsOpen} />;
}

export default function RequestFormWrapper() {
  return (
    <Suspense fallback={null}>
      <RequestFormInner />
    </Suspense>
  );
}
