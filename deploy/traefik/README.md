# Traefik — non utilisé en production CODIR

Traefik est **externe** sur le serveur de production : il tourne déjà comme
service partagé et écoute le réseau Docker `proxy`. CODIR s'y branche via les
labels Docker présents dans `docker-compose.prod.yml` (middlewares déclarés
inline avec le préfixe `codir-*`).

Les fichiers `traefik.yml` et `dynamic.yml` de ce dossier ne sont **pas montés**
par le compose prod. Ils sont conservés à titre de référence (par ex. pour un
déploiement standalone sans Traefik externe, ou pour un dev local autonome).

## Cas d'usage actuels

- **Prod (Traefik externe)** : ce dossier n'est pas utilisé. Les middlewares
  `codir-sec-headers`, `codir-rl`, `codir-rl-auth`, `codir-compress` sont
  définis via labels dans `docker-compose.prod.yml`.
- **Dev local** : `docker-compose.yml` à la racine inclut son propre service
  Traefik configuré via `--api.insecure=true` (HTTP-only, pas de TLS).
