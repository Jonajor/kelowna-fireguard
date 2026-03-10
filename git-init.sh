#!/bin/bash
set -e
git init
git add .
git commit -m "Initial commit — KelownaFireGuard AI Wildfire Warning System"
echo ""
echo "Local repo created. To push to GitHub:"
echo "  git remote add origin https://github.com/YOUR_USERNAME/kelowna-fireguard.git"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""
echo "Or with GitHub CLI:"
echo "  gh repo create kelowna-fireguard --public --source=. --push"
