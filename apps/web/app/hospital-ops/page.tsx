import { redirect } from "next/navigation";

export default function HospitalOpsPage() {
  redirect("/hospital-board?view=resources");
}
