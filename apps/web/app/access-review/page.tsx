import { AuthGuard } from "@/components/auth-guard";
import { AccessReviewWorkspaceV12, accessReviewRoles } from "@/components/access-review-workspace-v12";

export default function AccessReviewPage() {
  return <AuthGuard allowedRoles={accessReviewRoles}><AccessReviewWorkspaceV12 /></AuthGuard>;
}
