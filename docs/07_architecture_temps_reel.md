# 07 — Architecture temps réel

## 1. Cas d'usage temps réel dans CODIR

Plusieurs scénarios exigent du temps réel — par "temps réel" on entend une latence perçue inférieure à 500 ms entre l'événement et son rendu chez les utilisateurs concernés.

**Mode réunion live** : transcription qui défile au fur et à mesure, votes qui s'agrègent en direct, sujets qui passent au statut "traité" en synchrone pour tous les participants.

**Édition collaborative** : plusieurs participants éditent simultanément le PV provisoire, les notes d'un sujet, ou un plan d'action. Les curseurs, les sélections, et les modifications de texte sont propagés.

**Présence** : on voit qui est connecté, qui est en train de regarder le même document, qui est en réunion.

**Notifications live** : un risque critique remonte, une décision urgente est créée, un seuil KPI est franchi — l'écran ouvert se met à jour sans rafraîchissement.

**Dashboards live** : les KPI clés se rafraîchissent toutes les 10 à 60 secondes selon leur cadence, parfois en streaming pur (revenus de la journée, transactions).

**Activité utilisateurs** : feed d'activité côté admin et audit (qui fait quoi en temps réel).

## 2. Choix techniques

**Django Channels 4 (ASGI)** est le pivot. Il gère les WebSockets, est authentifié via le même mécanisme que l'API (middleware JWT custom), et bénéficie du couplage natif avec les models et l'ORM Django.

**Redis pub/sub** sert de transport pour la fan-out entre processus (channel layer). Le cluster Redis (3 nœuds) est dédié aux Channels et au Celery — pour scaling fort, on séparera.

**WebSocket protocole** au-dessus de TLS (WSS). Le format de message standardisé est un JSON `{type, payload, ts, request_id, idempotency_key?}`.

Alternatives écartées :

- **Socket.IO** apporte une couche d'abstraction utile mais introduit une dépendance non-Django et complique l'auth ; Channels suffit.
- **Server-Sent Events** est utile pour les flux unidirectionnels (ex. streaming d'une réponse IA) et **sera utilisé en complément** pour les sorties LLM en streaming, où la simplicité l'emporte.
- **WebTransport / WebRTC** : WebRTC sera utilisé spécifiquement pour le flux audio bidirectionnel des réunions multi-participants quand on veut limiter la dépendance à Zoom/Teams. WebTransport est sur la roadmap mais pas en v1.

## 3. Topologie

```
Client (web/mobile)                       Edge
    │                                       │
    │  WSS /ws/<scope>/?token=<jwt>          │
    ├──────────────────────────────────────► │
    │                                       │
    │                                  Traefik
    │                                       │
    │                                   sticky? non — channel layer Redis fan-out
    │                                       ▼
    │                              ASGI server (Daphne x N)
    │                                       │
    │                            ┌──────────┼──────────┐
    │                            │          │          │
    │                            ▼          ▼          ▼
    │                       Consumer A  Consumer B  Consumer C
    │                            │          │          │
    │                            └────┬─────┴────┬─────┘
    │                                 ▼          ▼
    │                          Channel layer Redis (pub/sub + groups)
    │                                 │          │
    │                                 ▼          ▼
    │                          Service apps (decisions, meetings…)
    │                                 ▲          ▲
    │                                 │          │
    │                          Celery workers / signals post_save
```

Les ASGI workers sont **stateless** par rapport aux WS (la session est portée par la connexion). N'importe quel ASGI worker peut servir n'importe quel client. La fan-out (ex. broadcast à tous les participants d'une réunion) passe par le channel layer Redis qui distribue à tous les workers qui ont des clients dans le groupe `meeting.<id>`.

## 4. Authentification WebSocket

Le client envoie le JWT en query parameter (les WS n'ont pas de header `Authorization` standard côté navigateur). Un middleware Channels `JWTAuthMiddleware` extrait, valide, et pose `scope["user"]` + `scope["organization"]`.

```python
# apps/realtime/middleware.py
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope["query_string"].decode())
        token = qs.get("token", [None])[0]
        try:
            UntypedToken(token)  # valide signature & expiry
            user = await self.get_user_from_token(token)
            org = await self.get_org_from_token(token)
        except (InvalidToken, TokenError):
            await send({"type": "websocket.close", "code": 4001})
            return
        scope["user"] = user
        scope["organization"] = org
        return await super().__call__(scope, receive, send)
```

## 5. Consumers — patrons types

### 5.1. NotificationConsumer (par utilisateur)

```python
# apps/notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            return await self.close(code=4001)
        self.group_name = f"user.{user.id}.notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # envoyer les non lues à la connexion
        await self.send_json({"type": "snapshot", "unread": await self.get_unread()})

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_event(self, event):
        await self.send_json(event["data"])
```

Les apps métier diffusent :

```python
# apps/notifications/services.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def push_notification(user_id, notification):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"user.{user_id}.notifications",
        {"type": "notification.event", "data": serialize(notification)},
    )
```

### 5.2. MeetingConsumer (live réunion)

```python
class MeetingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.meeting_id = self.scope["url_route"]["kwargs"]["meeting_id"]
        # autorisation
        ok = await is_participant(self.scope["user"], self.meeting_id)
        if not ok:
            return await self.close(code=4003)
        self.group = f"meeting.{self.meeting_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(self.group + ".presence", self.channel_name)
        await self.accept()
        await self.broadcast_presence(joined=True)

    async def disconnect(self, code):
        await self.broadcast_presence(joined=False)
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # ─── Réception client → action ──────────────────────────
    async def receive_json(self, content):
        kind = content.get("type")
        if kind == "vote":
            await self.handle_vote(content["payload"])
        elif kind == "note":
            await self.handle_note(content["payload"])
        elif kind == "presence.heartbeat":
            await self.handle_heartbeat()

    # ─── Diffusion server → clients ─────────────────────────
    async def meeting_event(self, event):    # transcript chunk, decision, vote update…
        await self.send_json(event["data"])

    async def broadcast_presence(self, joined: bool):
        await self.channel_layer.group_send(
            self.group + ".presence",
            {"type": "meeting.event", "data": {
                "type": "presence",
                "user_id": str(self.scope["user"].id),
                "joined": joined,
                "ts": now_iso(),
            }},
        )
```

### 5.3. DashboardConsumer

Souscrit à un dashboard. Les changements de KPI poussent des deltas. Le client n'a qu'à muter les valeurs des widgets, sans refetch.

## 6. Format de message standardisé

```json
{
  "type": "decision.created",
  "ts": "2026-05-13T10:24:11Z",
  "request_id": "req_01HXG5...",
  "actor": {"id": "u_123", "name": "C. Martin"},
  "payload": {
    "id": "d_98",
    "title": "Lancement projet Phoenix",
    "category": "stratégique",
    "priority": "critical"
  },
  "invalidate": ["decisions.detail.d_98", "meetings.detail.m_42"]
}
```

Le champ `invalidate` permet au front (Tanstack Query côté web, Riverpod côté mobile) de purger précisément les caches concernés.

## 7. Garanties de délivrance

WebSocket = best-effort par nature. Pour les événements à criticité forte :

- **Outbox pattern** côté serveur : on persiste l'événement dans une table puis on diffuse ; si la WS échoue, l'événement reste dans l'outbox et un Celery beat relance.
- **Sequence numbers** par groupe : chaque WS message porte un `seq`. Au reconnect, le client envoie son dernier `seq` et le serveur renvoie le delta.
- **Reconnect protocol** : le client maintient un dernier `seq` reçu et le passe en query au reconnect ; le serveur stocke 5 minutes de buffer par groupe dans Redis (TTL court, suffisant pour la majorité des micro-coupures).

## 8. Édition collaborative

Pour les notes et plans d'action édités en simultané, on adopte **CRDT light** : Yjs (Y.Doc) côté client + persistance backend via WebSocket avec relayage des updates Yjs binaires. Le backend ne fait que router (pas de fusion serveur), c'est résilient et offline-friendly. La persistance finale est exécutée au "save" explicite ou idle > 3 s.

L'alternative OT (Operational Transform) a été écartée : trop complexe pour le bénéfice, Yjs est mature et performant.

## 9. Présence et indicateurs

La présence est tenue par groupes nommés `<scope>.presence`. Heartbeat client toutes les 30 s. Sans heartbeat 90 s, on retire de la présence et on broadcast un événement `presence.left`. Affichage : avatar empilé sur les pages de réunion / de décision, indicateur de couleur dans la sidebar (vert = en ligne, ambre = inactif, gris = hors-ligne).

## 10. Streaming des réponses IA (SSE)

Pour le copilot IA, on utilise Server-Sent Events plutôt que WebSocket — le flux est unidirectionnel et il n'y a pas besoin de présence ou de groupes :

```http
GET /api/v1/ai/copilot/stream?conversation_id=c_42
Accept: text/event-stream

data: {"type":"token","text":"Le "}
data: {"type":"token","text":"chiffre "}
data: {"type":"token","text":"d'affaires"}
...
data: {"type":"citation","source":"doc_123","quote":"..."}
data: {"type":"done","usage":{"tokens_in":1240,"tokens_out":320}}
```

Côté Django, on utilise `StreamingHttpResponse` + `async def` + tunnel asyncio vers le provider IA.

## 11. Performance et limites

Capacité visée par ASGI worker (Daphne, 1 vCPU 1 Go) : **~ 8 000 WebSockets connectées idle**, **~ 2 000 actives** (envoi régulier). Sur cluster 4 workers : 32 000 connexions confortables. Au-delà : sharder par tenant ou passer à `uvicorn workers` + autoscaling.

Mesures Prometheus exposées : `ws_connections_total`, `ws_messages_sent_total`, `ws_messages_received_total`, `ws_group_size`, `ws_latency_ms` (par type d'événement).

## 12. Sécurité

- TLS 1.3 obligatoire, HSTS.
- Origin checking (les WS ne sont acceptées que pour les origines configurées par tenant).
- Rate limiting par utilisateur : max 50 messages/sec côté client, sinon close avec code 4029.
- Validation Zod (front) / DRF-like schemas (back) sur chaque message reçu.
- Audit : tout vote, toute édition de décision envoyée par WS est doublé d'une écriture en base (jamais d'action métier "WS only").

---

*Suite : [08 — Architecture sécurité](08_architecture_securite.md)*
