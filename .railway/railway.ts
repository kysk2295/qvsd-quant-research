import { defineRailway, project, service, volume } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "dashboard";
export default defineRailway(() => {
  const data = volume("dashboard-volume", { region: "europe-west4-drams3a", sizeMB: 5000 });
  const dashboard = service("dashboard", {
    build: { buildEnvironment: "V3", builder: "DOCKERFILE" },
    healthcheck: "/healthz",
    healthcheckTimeout: 60,
    volumeMounts: { "/data": data },
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 10 },
    replicas: { "europe-west4-drams3a": 1 },
  });

  return project("qvsd-research-lab", {
    variables: { managed: false },
    resources: [dashboard, data],
  });
});
