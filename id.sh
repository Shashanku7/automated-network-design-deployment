#!/usr/bin/env bash
set -euo pipefail

KC_URL="${KC_URL:-http://localhost:8180}"
REALM="${REALM:-cx-sol-build}"
GOOGLE_CLIENT_ID="${1:-}"
GOOGLE_CLIENT_SECRET="${2:-}"

echo "Waiting for Keycloak..."
until curl -sf "$KC_URL" > /dev/null 2>&1; do sleep 2; done

docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_URL" --realm master \
  --user admin --password admin

# Fix gateway client redirect URIs — allow any origin for dev/tunnel
CLIENT_ID=$(docker exec keycloak /opt/keycloak/bin/kcadm.sh get clients \
  -r "$REALM" -q clientId=gateway --fields id --format csv | tail -1)
if [ -n "$CLIENT_ID" ]; then
  docker exec keycloak /opt/keycloak/bin/kcadm.sh update "clients/$CLIENT_ID" \
    -r "$REALM" \
    -s 'redirectUris=["http://localhost:8080/*","http://localhost:5173/*","*"]'
  echo "Gateway client redirect URIs updated (wildcard added)."
fi

# Add Google IdP if credentials provided
if [ -n "$GOOGLE_CLIENT_ID" ] && [ -n "$GOOGLE_CLIENT_SECRET" ]; then
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
fi
