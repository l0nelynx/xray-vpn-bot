// Backend targets consume the base built from this checkout, including on PRs.
// No dependency on a mutable registry staging/latest tag between CI jobs.
group "default" {
  targets = ["bot", "support-bot", "dashboard", "miniapp", "frontend"]
}

target "_common" {
  context = "."
  pull = true
}

target "python-base" {
  inherits = ["_common"]
  dockerfile = "infra/docker/base.Dockerfile"
  tags = ["local/python-base:check"]
}

target "_backend" {
  inherits = ["_common"]
  contexts = { python-base = "target:python-base" }
  args = { BASE_IMAGE = "python-base" }
}

target "bot" {
  inherits = ["_backend"]
  // Override Compose's target-local argument even when Bake auto-loads it.
  args = { BASE_IMAGE = "python-base" }
  dockerfile = "infra/docker/bot.Dockerfile"
  tags = ["local/bot:check"]
}

target "support-bot" {
  inherits = ["_common"]
  dockerfile = "infra/docker/support_bot.Dockerfile"
  tags = ["local/support-bot:check"]
}

target "dashboard" {
  inherits = ["_backend"]
  args = { BASE_IMAGE = "python-base" }
  dockerfile = "infra/docker/dashboard.Dockerfile"
  tags = ["local/dashboard:check"]
}

target "miniapp" {
  inherits = ["_backend"]
  args = { BASE_IMAGE = "python-base" }
  dockerfile = "infra/docker/miniapp.Dockerfile"
  tags = ["local/miniapp:check"]
}

target "frontend" {
  inherits = ["_common"]
  dockerfile = "infra/docker/frontend.Dockerfile"
  tags = ["local/frontend:check"]
}
