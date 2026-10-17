# RoleSpace team workspace: a Docker dev container on coder-vm (private subnet, no public IP),
# with VS Code in the browser, the team's repos cloned, and Gemini CLI on the person's own
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

variable "repo_urls" {
  description = "Fallback when a person has no repo list on the VM: git repos (space-separated) cloned into ~/projects/<repo name>"
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
  # The repositories this person has access to (RoleSpace > Repo access), one git URL per line,
  # written by sync_build_keys.sh next to the key. Each gets a folder and its own buttons.
  repos_file = "/var/lib/rolespace/build-repos/${local.username}"
  repo_urls  = compact(split(fileexists(local.repos_file) ? "\n" : " ", fileexists(local.repos_file) ? trimspace(file(local.repos_file)) : var.repo_urls))
  repos      = { for u in local.repo_urls : trimsuffix(basename(u), ".git") => u }
  repo_names = [for u in local.repo_urls : trimsuffix(basename(u), ".git")]
  projects_port = 8770
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

    # Every project gets its own folder under ~/projects. A workspace made before projects keeps
    # its ~/project clone (and any work in it), shown among the others under its repo name.
    mkdir -p ~/projects
    if [ -d ~/project/.git ]; then
      name=$(basename "$(git -C ~/project remote get-url origin 2>/dev/null || echo project)" .git)
      [ -e ~/projects/$name ] || ln -s ~/project ~/projects/$name
    fi
    for url in ${join(" ", local.repo_urls)}; do
      name=$(basename "$url" .git)
      [ -e ~/projects/$name ] || git clone --depth 50 "$url" ~/projects/$name || echo "could not clone $url"
    done

    # The Projects page (projects.py): one row per repo, VS Code on one side, Gemini CLI on the other.
    mkdir -p ~/.rolespace
    echo "${base64encode(file("${path.module}/projects.py"))}" | base64 -d > ~/.rolespace/projects.py
    nohup python3 ~/.rolespace/projects.py ${local.projects_port} ${join(" ", local.repo_names)} > /tmp/projects.log 2>&1 &
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
  count        = data.coder_workspace.me.start_count
  source       = "registry.coder.com/coder/code-server/coder"
  version      = "~> 1.0"
  agent_id     = coder_agent.main.id
  folder       = "/home/coder/projects"
  display_name = "All repos"
  group        = "VS Code"
  order        = 90
}

# The Projects page: every repo as a row, with its VS Code and Gemini CLI side by side.
resource "coder_app" "projects" {
  agent_id     = coder_agent.main.id
  slug         = "projects"
  display_name = "Projects"
  icon         = "/icon/folder.svg"
  url          = "http://localhost:${local.projects_port}/"
  subdomain    = false
  share        = "owner"
  order        = 0
  healthcheck {
    url       = "http://localhost:${local.projects_port}/"
    interval  = 5
    threshold = 6
  }
}

# One VS Code and one Gemini CLI entry per repository, grouped, so Coder shows two tidy menus.
resource "coder_app" "code" {
  for_each     = local.repos
  agent_id     = coder_agent.main.id
  slug         = substr("code-${lower(replace(each.key, "/[^A-Za-z0-9]+/", "-"))}", 0, 32)
  display_name = each.key
  group        = "VS Code"
  icon         = "/icon/code.svg"
  url          = "http://localhost:13337/?folder=/home/coder/projects/${each.key}"
  subdomain    = false
  share        = "owner"
  order        = 1
}

resource "coder_app" "gemini" {
  for_each     = local.repos
  agent_id     = coder_agent.main.id
  slug         = substr("gemini-${lower(replace(each.key, "/[^A-Za-z0-9]+/", "-"))}", 0, 32)
  display_name = each.key
  group        = "Gemini CLI"
  icon         = "/icon/gemini.svg"
  command      = "cd ~/projects/${each.key} && gemini"
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
