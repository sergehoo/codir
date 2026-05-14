# 12 — WebSocket — protocole, scopes et événements

> Cette doc complète la doc 07 (architecture temps réel). Ici on documente précisément les **scopes** d'URL, les **types d'événements** échangés, et le **protocole** côté client.

## 1. URL et scopes

| Scope | URL | Authent | Cas d'usage |
|---|---|---|---|
| Notifications utilisateur | `/ws/notifications/` | JWT | Push notifications live (inapp) |
| Réunion | `/ws/meetings/<meeting_id>/` | JWT + check participant | Mode réunion live |
| Dashboard | `/ws/dashboards/<dashboard_id>/` | JWT + check permission view | KPI live |
| Recherche IA streaming | SSE `GET /api/v1/ai/copilot/conversations/<id>/messages/stream` | JWT | Tokens streaming réponse IA |
| Présence document | `/ws/documents/<doc_id>/presence/` | JWT + check view | Édition collaborative (Yjs) |
| Activité audit | `/ws/audit/feed/` | JWT (rôle audit) | Feed live d'activité |

Tous transport WSS (TLS 1.3). Token JWT en query parameter (`?token=eyJ...`) car le navigateur ne permet pas d'envoyer un header `Authorization` sur l'upgrade WS.

## 2. Format de message standardisé

Tous les messages — entrants et sortants — respectent l'enveloppe :

```json
{
  "type": "<event.type>",         // requis, kebab.dot
  "ts": "2026-05-13T10:24:11Z",   // serveur uniquement
  "id": "evt_01HXG5...",          // serveur uniquement, unique
  "seq": 4123,                    // serveur uniquement, monotone par scope
  "request_id": "req_...",        // facultatif, hérité du contexte HTTP si présent
  "idempotency_key": "uuid",      // requis pour les events mutants côté client
  "payload": { ... }              // forme spécifique au type
}
```

## 3. Catalogue d'événements — `/ws/notifications/`

**Server → Client** :

```
notification.new              { id, event_type, subject, body, priority, link }
notification.updated          { id, fields: { seen_at?, acted_at? } }
notification.removed          { id }
snapshot                      { unread: [...], cursor }
```

**Client → Server** :

```
notification.ack              { id }                  → marque comme vue
notification.heartbeat        { }                     → ping (toutes les 30 s)
```

## 4. Catalogue d'événements — `/ws/meetings/<id>/`

**Server → Client** :

```
presence                      { user_id, joined }
agenda.item.changed           { item_id, fields: {...} }
agenda.item.current           { item_id }            // changement de sujet en cours
transcript.chunk              { chunk_id, speaker, text, start_ts, end_ts, confidence }
transcript.correction         { chunk_id, new_text }
summary.live.update           { item_id, summary_md }
decision.proposed             { decision: {...} }     // décision créée
decision.updated              { id, fields: {...} }
decision.vote.cast            { decision_id, voter, choice, weight }
decision.vote.tally           { decision_id, yes, no, abstain, pending }
action.proposed               { action: {...} }
note.update                   { y_update_b64 }        // Yjs binary updates
hand.raised                   { user_id }
chairman.gavel                { action: "open|close|advance|recess" }
recording.state               { state: "recording|paused|stopped" }
meeting.ended                 { ended_at }
```

**Client → Server** :

```
vote.cast                     { decision_id, choice, weight?, proxy_for? }
note.update                   { y_update_b64 }
note.cursor                   { item_id, position }
hand.raise                    { }
hand.lower                    { }
presence.heartbeat            { }
audio.chunk                   { mp3_b64 | webrtc_track_id, start_ts }   // depuis salle
agenda.item.note.add          { item_id, text }
chairman.transition           { action }              // si chair
```

## 5. Catalogue d'événements — `/ws/dashboards/<id>/`

**Server → Client** :

```
widget.value.update           { widget_id, value, formatted, delta, trend }
widget.alert                  { widget_id, level: "warning|critical", message }
widget.config.changed         { widget_id, config: {...} }
dashboard.refresh             { reason }              // force pull complet
```

**Client → Server** :

```
subscribe.widgets             { widget_ids: [...] }   // narrow subscription
unsubscribe.widgets           { widget_ids: [...] }
```

## 6. Catalogue d'événements — `/ws/documents/<id>/presence/`

```
presence                      { user_id, name, color, joined }
cursor                        { user_id, anchor, head }
selection                     { user_id, ranges: [{anchor, head}] }
yjs.update                    { update_b64 }         // diff Yjs
yjs.sync.step1                { sv_b64 }              // state vector
yjs.sync.step2                { update_b64 }
```

## 7. Réconciliation, séquence et reconnect

Chaque scope produit des messages avec un `seq` monotone. Le client tient en mémoire le dernier `seq` reçu. À la reconnexion, il envoie immédiatement :

```json
{ "type": "sync.resume", "since_seq": 4123 }
```

Le serveur consulte le buffer Redis (5 min de fenêtre par scope) et renvoie le delta. Si `seq` trop ancien (gap > buffer), il répond `sync.gap` et le client fait un refetch HTTP complet.

## 8. Backoff de reconnexion

Stratégie : 0,5 s → 1 s → 2 s → 4 s → 8 s → 16 s → 30 s (cap). Jitter ±20 %.

Au reconnect réussi, refire toutes les actions client en outbox (les messages mutants idempotents stockés en attente, identifiés par `idempotency_key`).

## 9. Implémentation client (TypeScript)

```ts
// lib/ws/client.ts
type WSHandler = (msg: WSMessage) => void

export class WSClient {
  private ws?: WebSocket
  private lastSeq = 0
  private buffer: WSMessage[] = []
  private handlers = new Set<WSHandler>()
  private outbox: WSMessage[] = []
  private retryDelay = 500

  constructor(private url: string, private getToken: () => string) {}

  connect() {
    const wsUrl = `${this.url}?token=${this.getToken()}`
    this.ws = new WebSocket(wsUrl)
    this.ws.onopen = () => {
      this.retryDelay = 500
      if (this.lastSeq) this.send({ type: 'sync.resume', payload: { since_seq: this.lastSeq } })
      this.flushOutbox()
    }
    this.ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data)
      if (msg.seq) this.lastSeq = msg.seq
      this.handlers.forEach((h) => h(msg))
    }
    this.ws.onclose = () => this.scheduleReconnect()
    this.ws.onerror = () => this.ws?.close()
  }

  private scheduleReconnect() {
    setTimeout(() => this.connect(), this.retryDelay + Math.random() * this.retryDelay * 0.2)
    this.retryDelay = Math.min(this.retryDelay * 2, 30_000)
  }

  send(msg: Omit<WSMessage, 'ts' | 'seq' | 'id'>) {
    const enriched = { ...msg, idempotency_key: msg.idempotency_key ?? crypto.randomUUID() }
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(enriched))
    } else {
      this.outbox.push(enriched as WSMessage)
    }
  }

  private flushOutbox() {
    while (this.outbox.length && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(this.outbox.shift()))
    }
  }

  subscribe(h: WSHandler) {
    this.handlers.add(h)
    return () => this.handlers.delete(h)
  }
}
```

## 10. Implémentation côté Channels (consumer modèle)

```python
# apps/meetings/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.meetings.services import (
    is_participant, cast_vote, append_note, advance_chair,
)

class MeetingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        meeting_id = self.scope["url_route"]["kwargs"]["meeting_id"]
        if not await is_participant(user.id, meeting_id):
            return await self.close(code=4003)
        self.user_id = str(user.id)
        self.meeting_id = meeting_id
        self.group = f"org.{self.scope['organization'].id}.meeting.{meeting_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self._broadcast({"type": "presence", "payload": {"user_id": self.user_id, "joined": True}})

    async def disconnect(self, code):
        await self._broadcast({"type": "presence", "payload": {"user_id": self.user_id, "joined": False}})
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        t = content.get("type")
        idem = content.get("idempotency_key")
        if t == "vote.cast":
            result = await cast_vote(self.user_id, self.meeting_id, content["payload"], idem=idem)
            await self._broadcast({"type": "decision.vote.cast", "payload": result})
        elif t == "note.update":
            await append_note(self.meeting_id, content["payload"]["y_update_b64"])
            await self._broadcast({"type": "note.update", "payload": content["payload"]}, exclude_self=True)
        # ...

    async def meeting_event(self, event):
        await self.send_json(event["data"])

    async def _broadcast(self, data, exclude_self=False):
        await self.channel_layer.group_send(
            self.group,
            {"type": "meeting.event", "data": data, "exclude": self.channel_name if exclude_self else None},
        )
```

## 11. Sécurité

- Validation Pydantic (ou DRF schemas) sur chaque message entrant ; rejet `4400`.
- Rate-limit Redis 50 msg/s par client ; > 200 msg en 5 s → close `4029`.
- Audit : chaque vote / mutation passe par un service backend qui écrit en DB *avant* la rediffusion.
- Pas d'actions admin par WS (mutations admin restent HTTP avec MFA step-up si requis).

## 12. Observabilité

Métriques Prometheus exposées :

```
ws_connections_total{scope}
ws_active_connections{scope}
ws_messages_sent_total{type, scope}
ws_messages_received_total{type, scope}
ws_latency_ms{type}                 # latence application (réception → broadcast)
ws_disconnects_total{code}
ws_outbox_size{scope}
```

## 13. Tests

- Tests unitaires des consumers via `ChannelsLiveServerTestCase`.
- Tests d'intégration end-to-end : Playwright scénario "2 utilisateurs dans la même réunion votent" → assertion sur la propagation.
- Tests de charge : `wsbench` 10 000 connexions concurrentes idle + 2 000 actives, latence p99 cible < 200 ms.

---

*Suite : [13 — RBAC](13_rbac.md)*
