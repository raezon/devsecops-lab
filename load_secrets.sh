#!/bin/bash

# générer .env depuis vault
curl -s \
  --header "X-Vault-Token: $VAULT_TOKEN" \
  "$VAULT_ADDR/v1/secret/data/jenkins/config" | \
  jq -r '.data.data | to_entries[] | "\(.key)=\(.value)"' > .env

curl -s \
  --header "X-Vault-Token: $VAULT_TOKEN" \
  "$VAULT_ADDR/v1/secret/data/jenkins/pipeline" | \
  jq -r '.data.data | to_entries[] | "\(.key)=\(.value)"' >> .env