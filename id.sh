#!/usr/bin/env bash
set -euo pipefail

KC_URL="${KC_URL:-http://localhost:8080}"
REALM="${REALM:-cx-sol-build}"
GOOGLE_CLIENT_ID="${1:?Usage: $0 <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>}"
GOOGLE_CLIENT_SECRET="${2:?Usage: $0 <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>}"

echo "Waiting for Keycloak..."
until curl -sf "$KC_URL" > /dev/null 2>&1; do sleep 2; done

docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_URL" --realm master \
  --user admin --password admin

docker exec keycloak /opt/keycloak/bin/kcadm.sh create identity-provider/instances \
  -r "$REALM" \
  -s alias=google \
  -s providerId=google \
  -s displayName="Google" \
  -s enabled=true \
  -s config.clientId="$GOOGLE_CLIENT_ID" \
  -s config.clientSecret="$GOOGLE_CLIENT_SECRET" \
  -s config.defaultSyncMode=IMPORT \
  -s config.authorizationUrl=https://accounts.google.com/o/oauth2/v2/auth \
  -s config.tokenUrl=https://oauth2.googleapis.com/token

echo "Google IdP added to realm '$REALM'"
