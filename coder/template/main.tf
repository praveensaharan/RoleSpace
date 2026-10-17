# RoleSpace team workspace: a Docker dev container on coder-vm (private subnet, no public IP),
# with VS Code in the browser, the team repo cloned, and Gemini CLI on the person's own
# gateway key. The VM's service account can't call Vertex AI, so the gateway is the only way
# to a model.

terraform {
  required_providers {
    coder = {
      source = "coder/coder"
    }
    docker = {
      source = "kreuzwerker/docker"
    }
  }
}

variable "repo_url" {
  description = "Git repo cloned into ~/project on first start (empty = no clone)"
  type        = string
  default     = ""
}

variable "gateway_relay" {
  description = "Relay on the VM host that adds the VM's Google identity and forwards to the gateway"
  type        = string
  default     = "http://host.docker.internal:4000"
}

provider "docker" {}

data "coder_provisioner" "me" {}
data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

locals {
  username = data.coder_workspace_owner.me.name
  # Written by sync_build_keys.sh for Build-level people in role.yaml only.
  key_file    = "/var/lib/rolespace/build-keys/${local.username}"
  gateway_key = fileexists(local.key_file) ? trimspace(file(local.key_file)) : ""
}

resource "coder_agent" "main" {
  arch           = data.coder_provisioner.me.arch
  os             = "linux"
  startup_script = <<-EOT
    set -e
    if [ ! -f ~/.init_done ]; then
      cp -rT /etc/skel ~
      touch ~/.init_done
    fi

    # Gemini CLI signs in with the person's gateway key only. Google sign-in would
    # go straight to Google with their own account and skip the gateway.
    mkdir -p ~/.gemini
    cat > ~/.gemini/settings.json <<'JSON'
    {"security": {"auth": {"selectedType": "gemini-api-key"}},
     "privacy": {"usageStatisticsEnabled": false}}
    JSON

    if [ -n "${var.repo_url}" ] && [ ! -d ~/project/.git ]; then
      git clone --depth 50 "${var.repo_url}" ~/project
    fi
    mkdir -p ~/project
  EOT

  env = {
    GIT_AUTHOR_NAME            = coalesce(data.coder_workspace_owner.me.full_name, local.username)
    GIT_AUTHOR_EMAIL           = data.coder_workspace_owner.me.email
    GIT_COMMITTER_NAME         = coalesce(data.coder_workspace_owner.me.full_name, local.username)
    GIT_COMMITTER_EMAIL        = data.coder_workspace_owner.me.email
    GOOGLE_GEMINI_BASE_URL     = var.gateway_relay
    GEMINI_API_KEY             = local.gateway_key
    GEMINI_MODEL               = "gemini-pro"
    GEMINI_CLI_TRUST_WORKSPACE = "true"
  }

  metadata {
    display_name = "CPU Usage"
    key          = "0_cpu_usage"
    script       = "coder stat cpu"
    interval     = 10
    timeout      = 1
  }

  metadata {
    display_name = "RAM Usage"
    key          = "1_ram_usage"
    script       = "coder stat mem"
    interval     = 10
    timeout      = 1
  }
}

module "code-server" {
  count    = data.coder_workspace.me.start_count
  source   = "registry.coder.com/coder/code-server/coder"
  version  = "~> 1.0"
  agent_id = coder_agent.main.id
  folder   = "/home/coder/project"
  order    = 1
}

resource "coder_app" "gemini" {
  agent_id     = coder_agent.main.id
  slug         = "gemini"
  display_name = "Gemini CLI"
  icon         = "/icon/gemini.svg"
  command      = "cd ~/project && gemini"
  order        = 2
}

resource "docker_volume" "home_volume" {
  name = "coder-${data.coder_workspace.me.id}-home"
  lifecycle {
    ignore_changes = all
  }
  labels {
    label = "coder.owner"
    value = local.username
  }
  labels {
    label = "coder.workspace_id"
    value = data.coder_workspace.me.id
  }
}

resource "docker_container" "workspace" {
  count    = data.coder_workspace.me.start_count
  image    = "rolespace-workspace:v1"
  name     = "coder-${local.username}-${lower(data.coder_workspace.me.name)}"
  hostname = data.coder_workspace.me.name
  # Coder's access URL is localhost (people reach it through IAP); inside the container
  # that is the VM host.
  entrypoint = ["sh", "-c", replace(coder_agent.main.init_script, "/localhost|127\\.0\\.0\\.1/", "host.docker.internal")]
  env        = ["CODER_AGENT_TOKEN=${coder_agent.main.token}"]
  host {
    host = "host.docker.internal"
    ip   = "host-gateway"
  }
  volumes {
    container_path = "/home/coder"
    volume_name    = docker_volume.home_volume.name
    read_only      = false
  }
  labels {
    label = "coder.owner"
    value = local.username
  }
  labels {
    label = "coder.workspace_id"
    value = data.coder_workspace.me.id
  }

  lifecycle {
    precondition {
      # Template import does a dry run as the placeholder owner "default".
      condition     = local.gateway_key != "" || local.username == "default"
      error_message = "No gateway key for ${local.username}. Only people at the Build level in role.yaml get a workspace."
    }
  }
}
