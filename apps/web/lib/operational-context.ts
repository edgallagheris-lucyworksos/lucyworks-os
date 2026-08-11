export type OperationalContext = {
  premisesRef: string;
  siteName: string;
};

const PREMISES_KEY = "lucyworks.premisesRef";
const SITE_NAME_KEY = "lucyworks.siteName";

export function getOperationalContext(): OperationalContext {
  if (typeof window === "undefined") {
    return {
      premisesRef: process.env.NEXT_PUBLIC_PREMISES_REF || "default-premises",
      siteName: process.env.NEXT_PUBLIC_SITE_NAME || "Referral Hospital",
    };
  }

  const params = new URLSearchParams(window.location.search);
  const premisesFromUrl = params.get("premises")?.trim();
  const nameFromUrl = params.get("site")?.trim();
  const savedPremises = window.localStorage.getItem(PREMISES_KEY)?.trim();
  const savedName = window.localStorage.getItem(SITE_NAME_KEY)?.trim();

  const premisesRef = premisesFromUrl || savedPremises || process.env.NEXT_PUBLIC_PREMISES_REF || "default-premises";
  const siteName = nameFromUrl || savedName || process.env.NEXT_PUBLIC_SITE_NAME || "Referral Hospital";

  if (premisesFromUrl) window.localStorage.setItem(PREMISES_KEY, premisesFromUrl);
  if (nameFromUrl) window.localStorage.setItem(SITE_NAME_KEY, nameFromUrl);

  return { premisesRef, siteName };
}
