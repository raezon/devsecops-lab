#!/bin/bash

# =============================================================
#  Load Secrets from Vault
#  Usage: source ./load-secrets.sh
# =============================================================

if [ -z "$VAULT_ADDR" ]; then
    export VAULT_ADDR='http://127.0.0.1:8200'
fi

if [ -z "$VAULT_TOKEN" ]; then
    echo "❌ VAULT_TOKEN n'est pas défini"
    echo "Lance: export VAULT_TOKEN='yourtoken'"
    return 1 2>/dev/null || exit 1
fi

echo "🔐 Chargement des secrets depuis Vault..."

if ! curl -s "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1; then
    echo "❌ Vault n'est pas accessible"
    return 1 2>/dev/null || exit 1
fi

# lire depuis vault
CONFIG=$(curl -s \
    --header "X-Vault-Token: $VAULT_TOKEN" \
    "$VAULT_ADDR/v1/secret/data/jenkins/config")

PIPELINE=$(curl -s \
    --header "X-Vault-Token: $VAULT_TOKEN" \
    "$VAULT_ADDR/v1/secret/data/jenkins/pipeline")
# On utilise tee pour écrire dans le fichier tout en laissant passer le texte vers la variable
tst=$(echo $PIPELINE | jq -r '.data.data.openrouter_api_key' )

# Maintenant ça va marcher
echo "Valeur capturée : $tst"
# exporter avec jq
export JENKINS_ADMIN_USER=$(echo "$CONFIG" | jq -r '.data.data.admin_user')
export JENKINS_ADMIN_PASSWORD=$(echo "$CONFIG" | jq -r '.data.data.admin_password')
export JENKINS_AGENT_SECRET=$(echo "$CONFIG" | jq -r '.data.data.agent_secret')
export OPENROUTER_API_KEY=$(echo "$PIPELINE" | jq -r '.data.data.openrouter_api_key')
export RESEND_API_KEY=$(echo "$PIPELINE" | jq -r '.data.data.resend_api_key')
export REPORT_EMAIL=$(echo "$PIPELINE" | jq -r '.data.data.report_email')

echo "✅ Secrets chargés depuis Vault:"
echo "  VAULT_ADDR           = $VAULT_ADDR"
echo "  JENKINS_ADMIN_USER   = $JENKINS_ADMIN_USER"
echo "  REPORT_EMAIL         = $REPORT_EMAIL"
echo "  JENKINS_AGENT_SECRET = [hidden]"
echo "  OPENROUTER_API_KEY   = [hidden]"
echo "  RESEND_API_KEY       = [hidden]"
