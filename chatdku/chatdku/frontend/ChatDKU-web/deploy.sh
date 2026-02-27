#!/usr/bin/env bash
set -euo pipefail

# Colors
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

APP_DIR="/var/www/chatdku"
BACKUP_DIR="/var/www/chatdku_webapp_backups"
BUILD_DIR="out"  # where `npm run build` outputs

# cd /path/to/frontend

echo -e "${BLUE}${BOLD}==> Running tests...${RESET}"
if npm run test; then
  echo -e "${GREEN}${BOLD}==> Tests passed.${RESET}"
else
  echo -e "${RED}${BOLD}==> Tests failed.${RESET}"
  read -r -p "$(echo -e "${YELLOW}Tests failed. Deploy anyway? [y/N]: ${RESET}")" force
  case "$force" in
    [Yy]* )
      echo -e "${YELLOW}${BOLD}==> Proceeding with deploy despite failing tests.${RESET}"
      ;;
    * )
      echo -e "${YELLOW}${BOLD}==> Aborting deploy because tests failed.${RESET}"
      exit 1
      ;;
  esac
fi

echo
read -r -p "$(echo -e "${CYAN}Deploy this build? [y/N]: ${RESET}")" answer
case "$answer" in
  [Yy]* )
    echo -e "${GREEN}${BOLD}==> Proceeding with deploy...${RESET}"
    ;;
  * )
    echo -e "${YELLOW}${BOLD}==> Aborting deploy.${RESET}"
    exit 0
    ;;
esac

echo -e "${BLUE}${BOLD}==> Running build...${RESET}"
npm run build

timestamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -d "$APP_DIR" ]; then
  echo -e "${BLUE}${BOLD}==> Creating backup at ${BACKUP_DIR}/${timestamp}/${RESET}"
  sudo rsync -av --delete "$APP_DIR"/ "${BACKUP_DIR}/${timestamp}/"
else
  echo -e "${YELLOW}${BOLD}==> Warning:${RESET} ${YELLOW}${APP_DIR} does not exist; skipping backup.${RESET}"
fi

echo -e "${BLUE}${BOLD}==> Deploying new build to ${APP_DIR}/ ${RESET}"
sudo rsync -av --delete "${BUILD_DIR}/" "${APP_DIR}/"

echo -e "${GREEN}${BOLD}==> Deploy complete.${RESET}"

