# EKS learning plan for Zipp

This is a hands-on plan for running the existing application stack on Amazon EKS from a GitHub-hosted repository. The first cluster is disposable: create it for a focused learning session, keep any wanted reports outside the cluster, and delete it afterward. The repository has a GitHub Actions CI workflow, but no EKS deployment configuration or ECR publishing workflow.

**Current image status:** CI builds the API and frontend images without publishing them. ECR publication has been completed outside this repository, according to the project owner. Record the AWS Region, image references and digests, and the publishing method before using those images in EKS values.

**Project status:** ECR publication and EKS cluster setup are complete outside this repository, as confirmed by the project owner. Application deployment to EKS, GitHub Actions publishing/deployment, and EKS load/cleanup exercises are deferred. The local application project is complete without these steps.

## What I want to learn

By the end, I should be able to explain and demonstrate:

1. How GitHub source becomes versioned API and frontend container images in Amazon ECR.
2. How GitHub Actions can obtain short-lived AWS credentials through OIDC if publishing is automated.
3. How an EKS control plane, managed node group, VPC, IAM access entry, and `kubeconfig` fit together.
4. How EBS-backed PersistentVolumeClaims support PostgreSQL, Kafka, Valkey, and Prometheus.
5. How Helm installs this stack, runs the migration Job, and reports deployment failures.
6. How to inspect application, Kafka, and observability behavior under load.
7. How to find and remove every billable resource after an experiment.

Keep the first pass to **one EKS cluster, one managed EC2 node, and one application replica**. This is for learning, not high availability. Kafka remains a single broker/controller, and the API process still contains the Kafka consumer.

## Cost and session model

I expect to use the environment for **10–20 hours per month**. An EKS cluster under standard Kubernetes version support costs **$0.10 per cluster-hour** while it exists. Scaling its node group to zero does not stop that control-plane charge. A cluster kept for a 730-hour month costs about **$73 for EKS alone**; a cluster that exists for only 10–20 hours incurs about **$1–$2 in EKS control-plane charges**, plus EC2, EBS, public IPv4, data transfer, and any other resources. Rates vary by region and can change. See [EKS pricing](https://aws.amazon.com/eks/pricing/).

For the first run, choose one AWS Region and calculate the full estimate there before creating anything. Use the [AWS Pricing Calculator](https://calculator.aws/) for the selected node, EBS volumes, and networking. `eksctl` creates two worker nodes by default if its configuration is left implicit, and its default VPC configuration includes a NAT gateway. Specify the node count and NAT choice explicitly. NAT has an hourly charge while provisioned; see the [eksctl cluster](https://docs.aws.amazon.com/eks/latest/eksctl/creating-and-managing-clusters.html) and [VPC configuration](https://docs.aws.amazon.com/eks/latest/eksctl/vpc-configuration.html) guides.

**Session rule:** note the creation time and a planned deletion time before starting. Set an AWS Budget alert, then check the Cost Explorer and resource inventory after cleanup. Keep ECR images between sessions only if their small ongoing storage cost is acceptable.

## Target flow

```text
GitHub commit
  -> GitHub Actions: checks and builds API + frontend images (current)
  -> separate publication step -> Amazon ECR (completed outside this repo)
  -> EKS managed node pulls both images
  -> Helm: Strimzi, monitoring, application stack
  -> EBS volumes: PostgreSQL, Kafka, Valkey, Prometheus

Laptop kubectl -> EKS API -> pods, logs, port-forward
Load generator -> application Service -> PostgreSQL / Kafka / Valkey
```

Start with a **manual deployment from the laptop** using the published images. Add GitHub-driven deployment only after the manual path works. This keeps build identity, cluster access, and Kubernetes behavior understandable one step at a time.

## Phase 0 — GitHub baseline (complete)

**Learn:** repository history, branch protection, Actions permissions, and what is safe to publish.

- `.github/workflows/ci.yml` runs frontend and Python checks, Helm validation, both image builds, and secret scans. It has read-only repository permissions and no AWS deployment credentials.
- `.gitignore` and the repository Git hooks guard against committing local environment files, generated reports, and likely secrets. Review staged files before each push.
- Record the GitHub repository, default branch, AWS account, Region, and planned cluster name in a local worksheet. Do not put credentials in the repository.

**Status:** implemented and running in `.github/workflows/ci.yml`.

## Phase 1 — ECR image publication (complete outside this repository)

**Learn:** ECR image references, tags/digests, and the current publishing method; IAM trust and GitHub OIDC if publishing is automated.

- [x] Publish the API and frontend images to ECR outside this repository (completed by the project owner).
- Before an EKS application deployment, record the ECR image references, AWS Region, tags or digests, source commit, and publishing method. The API uses the root `Dockerfile`; the frontend uses `frontend/Dockerfile` and public Vite build arguments.
- Verify worker-role pull access during the deferred EKS deployment. See the [ECR push guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html).
- If image publishing should become automatic, add a separate trusted-branch workflow. Use a restricted GitHub OIDC role with ECR push permissions and capture the resulting image digests. Pull requests should continue to run checks without AWS write access. Confirm the actual OIDC `sub` format before writing the trust condition. See [GitHub's AWS OIDC guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) and the [AWS credentials action](https://github.com/aws-actions/configure-aws-credentials).

**Status:** image publication is complete. Recording image provenance and verifying worker-node pull access remain deployment-time tasks. GitHub-driven publishing is optional and is not present in this repository.

## Phase 2 — EKS cluster setup (complete outside this repository)

**Learn:** control plane vs worker node, managed node groups, VPC routing, cluster endpoint access, and IAM access entries.

The project owner has confirmed the cluster setup is complete. Its Region, node sizing, endpoint access, IAM access method, and networking details are not recorded in this repository. Review those settings before deploying the app. Do not create another cluster as part of the current project scope. References: [EKS access entries](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html), [endpoint access](https://docs.aws.amazon.com/eks/latest/eksctl/vpc-cluster-access.html), and [kubeconfig](https://docs.aws.amazon.com/eks/latest/userguide/create-kubeconfig.html).

**Status:** cluster setup is complete per the project owner; app-specific compatibility review is deferred.

## Phase 3 — Prepare storage and repo-specific EKS values (deferred)

**Learn:** EBS CSI, StorageClasses, PVC lifecycle, and the difference between local and AWS image delivery.

- Install the Amazon EBS CSI driver as an EKS add-on with the required IAM permissions, preferably through EKS Pod Identity. Create or select a gp3 StorageClass. See the [EBS CSI guide](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html).
- Add separate Helm values for EKS. Preserve the current Minikube values. Replace both local image repositories/tags and `pullPolicy: Never` with the API and frontend ECR images and an appropriate pull policy. Use a SHA tag or digest for each deployment.
- Set an EKS StorageClass for PostgreSQL, Kafka, Valkey, and Prometheus. The current Prometheus values explicitly use Minikube's `standard` class; Kafka, PostgreSQL, and Valkey also create PVCs. Confirm all PVCs bind before waiting on application readiness.
- Add EKS-specific Make targets or a script that use the EKS kubecontext and values files. Existing `make infra-up` and `make deploy` start Minikube and load a local image, so they are not EKS deployment commands.
- Keep application and database passwords out of GitHub. For the first manual deployment, create Kubernetes Secrets from a local, Git-ignored file. Later, learn AWS Secrets Manager and a suitable sync mechanism as a separate exercise. Do not have the image-build workflow handle application secrets.

**Done when:** a rendered EKS chart points to ECR and the EBS StorageClass, with no Minikube startup or local image loading in its path.

## Phase 4 — Deploy and inspect the application (deferred)

**Learn:** Helm releases, CRDs/operators, migration Jobs, readiness, and recovery.

1. Install the Strimzi operator and wait for its CRDs/operator to be ready.
2. Install Prometheus/Grafana with EKS storage values. Confirm Prometheus's PVC binds.
3. Create the application namespace and Secrets, then install the umbrella chart.
4. Watch PostgreSQL, Kafka, Valkey, the migration Job, and the application pod. The migration Job must finish before treating the deployment as ready.
5. Synchronize the generated Kafka user password into the application Secret using an EKS-safe workflow, then restart the application as required by the current design.
6. Verify the API, a short-link redirect, a consumed visit event, and the provisioned Grafana dashboard. Read pod logs and Kubernetes events when any step fails.

Keep services internal at first. Use `kubectl port-forward` for the API and Grafana. Learn ingress and the AWS Load Balancer Controller later if a public endpoint is actually needed; an externally exposed load balancer adds both setup and cost.

**Done when:** a link can be created and visited, the visit is persisted, and Grafana shows the relevant metrics.

## Phase 5 — Run one measured EKS load experiment (deferred)

**Learn:** requests vs limits, HPA prerequisites, metrics interpretation, and cost/performance tradeoffs.

- API load testing is complete for the local application. If the EKS deployment resumes, run one existing Locust preset against the cluster. Put the load generator near the cluster for performance measurements rather than sending load through `kubectl port-forward`.
- Capture the Locust HTML/CSV report, pod restart reasons, CPU/memory working sets, throttling, Kafka lag, database behavior, and Prometheus target health. Keep reports outside the cluster before teardown.
- Compare observed peaks with the limits in the EKS values. Change one limit or replica setting at a time and explain the effect. A single Kafka broker and application-embedded consumer are deliberate constraints of this experiment.
- Treat HPA, multiple application replicas, public ingress, and managed databases as follow-up exercises after the baseline is understood.

**Done when:** the load report and Kubernetes/Grafana observations support a short written explanation of the bottleneck and the next change.

## Phase 6 — Tear down and account for cost (deferred)

**Learn:** resource ownership, deletion order, persistent data lifecycle, and billing verification.

- Export anything worth keeping: load reports, notes, relevant logs, and, only if needed, database or metrics backups. Cluster deletion is allowed to discard experimental data.
- Remove any Kubernetes `LoadBalancer` Services or Ingress resources before deleting the cluster, if created. Inspect Helm releases, PVCs/PVs, EBS volumes, snapshots, load balancers, NAT gateways, public IPs, and CloudFormation stacks. AWS's [EKS deletion guide](https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html) calls out load balancers and other resources that can outlive the cluster.
- Delete the cluster with the matching `eksctl` configuration, then confirm the cluster and node group are gone. Check the AWS resource inventory and billing view afterward. Keep or delete ECR images intentionally.
- Record total cluster lifetime, EC2 runtime, storage/network resources, and actual cost for the session. Update the estimate for the next run.

**Done when:** no unintended EKS, EC2, EBS, load-balancer, NAT, or public-IP charge remains, and the session has a saved cost/performance note.

## Files to add when implementing

| Proposed file | Purpose |
| --- | --- |
| `deploy/eks/cluster.yaml` | Explicit, disposable `eksctl` cluster configuration |
| `deploy/eks/values-stack.yaml` | Both ECR images and EKS storage overrides for the umbrella chart |
| `deploy/eks/values-monitoring.yaml` | EKS Prometheus storage overrides |
| `.github/workflows/image.yml` | Optional OIDC-authenticated ECR build and push |
| `scripts/eks-deploy.sh` or EKS Make targets | Manual, context-aware deployment sequence |
| `scripts/eks-cleanup.sh` or a runbook | Explicit teardown and leftover-resource checks |

Do not add a GitHub deployment workflow until a manual deploy, access check, and teardown have each worked once. At that point, grant its role only the EKS and Kubernetes permissions needed for deployment, separate from the ECR build role.
