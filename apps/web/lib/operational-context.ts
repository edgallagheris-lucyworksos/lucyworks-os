"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";

export type OperationalContext = {
  organisationRef?: string;
  siteRef?: string;
  premisesRef: string;
  siteName: string;
  version?: number;
};

type AuthorisedContextResponse = {
  context?: {
    organisationRef?: string;
    siteRef?: string;
    premisesRef?: string;
    version?: number;
  };
  sites?: Array<{
    siteRef?: string;
    premisesRef?: string;
    name?: string;
  }>;
};

const fallbackContext: OperationalContext = {
  premisesRef: process.env.NEXT_PUBLIC_PREMISES_REF || "default-premises",
  siteName: process.env.NEXT_PUBLIC_SITE_NAME || "Referral Hospital",
};

export function getOperationalContext(): OperationalContext {
  return fallbackContext;
}

export async function loadOperationalContext(): Promise<OperationalContext> {
  const payload = await apiGet<AuthorisedContextResponse>("/api/v26/context");
  const authorised = payload.context;
  if (!authorised?.premisesRef) throw new Error("No authorised hospital context");

  const site = (payload.sites || []).find(item =>
    item.siteRef === authorised.siteRef || item.premisesRef === authorised.premisesRef
  );

  return {
    organisationRef: authorised.organisationRef,
    siteRef: authorised.siteRef,
    premisesRef: authorised.premisesRef,
    siteName: site?.name || fallbackContext.siteName,
    version: authorised.version,
  };
}

export function useOperationalContext(): OperationalContext {
  const [context, setContext] = useState<OperationalContext>(fallbackContext);

  useEffect(() => {
    let active = true;
    loadOperationalContext()
      .then(value => { if (active) setContext(value); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return context;
}
