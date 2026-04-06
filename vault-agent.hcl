# =============================================================
#  Vault Agent Configuration
# =============================================================

# adresse vault
vault {
  address = "http://host.docker.internal:8200"
}

# authentification
auto_auth {
  method "token" {
    config = {
      token = "mydevtoken"
    }
  }

  sink "file" {
    config = {
      path = "/vault/secrets/.token"
      mode = 0640
    }
  }
}

# générer fichier .env pour jenkins
template {
  contents = <<EOT
{{ with secret "secret/data/jenkins/config" }}
JENKINS_ADMIN_USER={{ .Data.data.admin_user }}
JENKINS_ADMIN_PASSWORD={{ .Data.data.admin_password }}
JENKINS_AGENT_SECRET={{ .Data.data.agent_secret }}
{{ end }}
{{ with secret "secret/data/jenkins/pipeline" }}
OPENROUTER_API_KEY={{ .Data.data.openrouter_api_key }}
RESEND_API_KEY={{ .Data.data.resend_api_key }}
REPORT_EMAIL={{ .Data.data.report_email }}
{{ end }}
EOT
  destination = "/vault/secrets/jenkins.env"
  perms       = 0640
}

# mode daemon
cache {
  use_auto_auth_token = true
}