# 05 — Architecture mobile (Flutter)

## 1. Positionnement du mobile dans l'écosystème CODIR

Le mobile n'est pas un "compagnon léger" du web : c'est l'**outil de pilotage en mouvement** du dirigeant. Il doit assurer ce qu'un DG fait entre deux réunions, dans une voiture, dans un avion, dans un ascenseur : valider une décision, signer un document, consulter un KPI critique, recevoir une alerte risque, voter à distance, prendre une note rapide en réunion. Trois exigences en découlent : **vitesse perçue extrême** (chaque interaction < 200 ms), **continuité offline-first** (tout doit marcher sans réseau et se synchroniser silencieusement), **sécurité forte avec biométrie**.

## 2. Stack technique

| Composant | Version | Rôle |
|---|---|---|
| Flutter | 3.24 LTS | Framework UI cross-platform |
| Dart | 3.5 | Langage |
| Riverpod | 2.x | State management + DI |
| go_router | 14.x | Routing déclaratif |
| dio | 5.x | HTTP client |
| web_socket_channel | 3.x | WebSockets |
| hive_ce + isar | dernière | Base locale offline (NoSQL chiffré) |
| drift (sqlite) | 2.x | Base relationnelle pour cache structuré |
| local_auth | 2.x | Biométrie (FaceID, TouchID, empreintes Android) |
| flutter_secure_storage | 9.x | Stockage tokens chiffré OS keychain |
| firebase_messaging | dernière | Push notifications |
| sentry_flutter | dernière | Crash reporting |
| fl_chart + syncfusion_charts | dernière | Charts performants |
| flutter_localizations + intl | — | i18n |
| package_info_plus, device_info_plus, connectivity_plus | — | OS info, réseau |

## 3. Architecture en couches

```
mobile/
├── lib/
│   ├── main.dart
│   ├── app.dart                          ← MaterialApp + theming
│   ├── core/
│   │   ├── api/                          ← dio, intercepteurs, refresh JWT
│   │   ├── auth/                         ← biométrie, secure storage
│   │   ├── ws/                           ← WS manager
│   │   ├── offline/                      ← sync engine
│   │   ├── theme/
│   │   ├── i18n/
│   │   ├── permissions/                  ← RBAC local
│   │   └── utils/
│   ├── data/                             ← repositories + sources
│   │   ├── meetings/
│   │   │   ├── meeting_repository.dart
│   │   │   ├── meeting_local_source.dart  (Hive)
│   │   │   └── meeting_remote_source.dart (dio)
│   │   ├── decisions/
│   │   ├── action_plans/
│   │   ├── documents/
│   │   ├── kpis/
│   │   └── notifications/
│   ├── domain/                           ← entités + cas d'usage
│   │   ├── entities/
│   │   ├── usecases/
│   │   └── failures/
│   ├── presentation/                     ← écrans + widgets + providers
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── meetings/
│   │   ├── decisions/
│   │   ├── action_plans/
│   │   ├── documents/
│   │   ├── ai_copilot/
│   │   ├── notifications/
│   │   ├── settings/
│   │   └── shared/
│   └── routing/
│       └── app_router.dart
├── pubspec.yaml
└── test/
```

Le projet adopte **Clean Architecture light** : `presentation → domain → data`. La couche `domain` ne dépend que de Dart. La couche `data` implémente les contrats du domain. La couche `presentation` consomme via Riverpod providers.

## 4. State management — Riverpod

Trois familles de providers :

**`Provider`** pour les dépendances et services (`apiClientProvider`, `wsManagerProvider`).
**`StateNotifierProvider` / `AsyncNotifierProvider`** pour les états applicatifs (auth, sync, filtres).
**`FutureProvider.family` / `StreamProvider.family`** pour les requêtes de données (listes de décisions, détail meeting).

```dart
// presentation/decisions/decisions_providers.dart
final decisionsListProvider = AsyncNotifierProvider.family<
    DecisionsListNotifier, List<Decision>, DecisionsFilter>(
  DecisionsListNotifier.new,
);

class DecisionsListNotifier extends FamilyAsyncNotifier<List<Decision>, DecisionsFilter> {
  @override
  Future<List<Decision>> build(DecisionsFilter filter) async {
    final repo = ref.watch(decisionsRepositoryProvider);
    // 1. fast path : cache local
    final cached = await repo.fetchLocal(filter);
    if (cached.isNotEmpty) state = AsyncValue.data(cached);
    // 2. revalidation réseau
    final fresh = await repo.fetchRemote(filter);
    await repo.cacheLocal(fresh);
    return fresh;
  }

  Future<void> vote(String decisionId, VoteChoice choice) async {
    final repo = ref.read(decisionsRepositoryProvider);
    state = AsyncValue.data(applyOptimistic(state.requireValue, decisionId, choice));
    try {
      await repo.vote(decisionId, choice);
      ref.invalidateSelf();
    } catch (e) {
      ref.invalidateSelf();
      rethrow;
    }
  }
}
```

## 5. Sync engine — offline first

Le moteur de synchronisation est le cœur de l'expérience mobile.

**Read path :** chaque écran lit d'abord depuis Hive/Isar (instantané), puis lance une requête réseau en arrière-plan et met à jour la base locale, puis le state Riverpod émet la nouvelle version. Si pas de réseau, l'utilisateur voit la donnée locale avec un indicateur "synchronisé il y a X minutes".

**Write path :** toute écriture (vote, note, validation de tâche) est écrite localement dans une `outbox` (table dédiée Drift). Un service Dart `OutboxSyncService` essaie de transmettre au backend dès que le réseau revient, avec stratégie d'exponential backoff et idempotency key UUID. En cas de conflit, la résolution est : *last-write-wins* pour les notes, *server-wins* pour les décisions critiques (le serveur est l'autorité), *manual-merge* pour les documents collaboratifs.

**Delta sync :** un endpoint `GET /api/v1/sync/delta?since=<cursor>&types=meetings,decisions` retourne les changements depuis le dernier curseur connu. Format compact (champs réduits, payload binaire MessagePack en option). L'utilisateur peut forcer un *full resync*.

```dart
// core/offline/outbox_sync_service.dart
class OutboxSyncService {
  Future<void> flush() async {
    final pending = await db.outbox.where((o) => o.status == 'pending').get();
    for (final op in pending) {
      try {
        await api.execute(op);
        await db.outbox.update(op.id, status: 'sent', syncedAt: DateTime.now());
      } on ConflictException catch (e) {
        await _resolveConflict(op, e.serverState);
      } on NetworkException {
        return; // backoff côté caller
      }
    }
  }
}
```

## 6. Authentification mobile

Login : email + mot de passe + MFA (TOTP, push approval, ou WebAuthn via plateforme).
**Une fois authentifié**, l'utilisateur active la **biométrie** (`local_auth`) pour les sessions suivantes : le refresh token est conservé dans `flutter_secure_storage` (Keychain iOS / Keystore Android), accessible uniquement après prompt biométrique.
**Timeout d'inactivité** : 5 minutes (configurable par tenant) → re-prompt biométrique sans déconnexion. Logout serveur effectif si refresh expire ou si l'admin révoque la session.
**Détection de jailbreak / root** via `flutter_jailbreak_detection` — bloquant pour les éditions Enterprise/Sovereign.

## 7. Navigation

`go_router` déclaratif, routes typées via classes. Bottom navigation avec 5 onglets primaires :

```
[Dashboard]  [Réunions]  [Décisions]  [Mon agenda]  [Plus]
```

Chaque onglet maintient son stack de navigation indépendant. Deep links supportés (`codir://meeting/abc123` pour passer d'une notification au détail).

## 8. UI — design system mobile

Adapter le design system web sans le copier servilement. Le mobile privilégie :

- **Cartes pleine largeur** plutôt que grilles denses
- **Pull-to-refresh** systématique
- **Bottom sheets** pour les actions secondaires plutôt que des modaux
- **Gestes** : swipe pour archiver une notification, swipe pour voter rapide, long-press pour action contextuelle
- **Haptique** : confirmation tactile sur les actions critiques (vote, validation)
- **Typography mobile** : Inter (web) → SF Pro / Roboto natifs en accent pour respecter les conventions OS

Theming clair/sombre/système, respecte la préférence OS.

## 9. Mode réunion mobile

C'est l'écran le plus important du mobile. Quand l'utilisateur ouvre une réunion en cours, il accède à :

- **En-tête** : heure, titre, présents (avatars empilés), bouton "Lever la main"
- **Onglet "Live"** : transcription temps réel, surlignée par locuteur, défilante avec auto-scroll lock désactivable
- **Onglet "Ordre du jour"** : sujets, sujet en cours mis en avant, possibilité de prendre des notes privées par sujet
- **Onglet "Décisions"** : décisions proposées, vote OUI / NON / ABSTENTION avec confirmation biométrique optionnelle (option du tenant pour les décisions sensibles)
- **Onglet "Actions"** : tâches générées en live, possibilité d'accepter ou refuser l'assignation
- **Onglet "Docs"** : pièces jointes consultables hors connexion (téléchargées en arrière-plan dès la convocation)

WebSocket maintenu en arrière-plan pendant 30 minutes hors app (mode Picture-in-Picture pour la transcription sur iOS 16+ et Android 14+).

## 10. Notifications push

Firebase Cloud Messaging (FCM) côté Android, APNs côté iOS, **Huawei Push** pour les marchés où c'est nécessaire (édition Sovereign).

Catégories de notifications :
- **Critique** (décision urgente, KPI breach rouge, risque critique) : son fort, contourne le mode silencieux côté iOS si entitlement *Time-Sensitive*.
- **Importante** (convocation, validation requise, assignation) : son standard.
- **Information** (commentaire, mention) : silencieuse.

Actions inline : un push "Validation requise sur la décision X" permet de **valider directement** depuis la notification sans ouvrir l'app (action contextuelle iOS / Android), authentifiée par biométrie. C'est la fonctionnalité signature de CODIR mobile.

## 11. Dashboard mobile exécutif

Différent du web : on ne reproduit pas un grand cockpit. On présente **6 KPI majeurs** sous forme de cartes plein écran swipeables (Today widget style), chacune avec drill-down :

```
┌───────────────────────┐
│   KPI #1              │
│   Revenu mensuel      │
│   +12,4 % vs M-1     ▲│
│   ▁▃▅▆▇▇▆            │
│   Voir détail →      │
└───────────────────────┘
        • • • • • •
```

Sous les cartes, trois sections rapides :

- **Mes décisions en attente** (max 5)
- **Mes actions du jour**
- **Prochaine réunion CODIR**

## 12. Performance mobile — cibles

| Indicateur | Cible |
|---|---|
| Cold start | < 1,8 s sur iPhone 12 / Pixel 6 |
| Warm start | < 600 ms |
| Frame rate scrolling | 60 fps soutenu, 90/120 fps sur device capables |
| Taille APK / IPA | < 35 MB |
| Consommation mémoire stable | < 220 MB |
| Battery drain réunion 1 h live (WS + transcription affichée) | < 8 % |

## 13. Tests

Tests unitaires (`flutter_test`) sur le domaine et les services. Tests de widgets sur les composants critiques. Tests d'intégration (`integration_test` package) pour les flux clés. Tests visuels via `golden_toolkit`.

## 14. Distribution

Build et signature CI : GitHub Actions → Fastlane → TestFlight (iOS) et Google Play Internal Testing. Promotion en bêta puis prod via Fastlane lanes paramétrées. Édition Sovereign : déploiement MDM (Intune, Workspace ONE) avec configuration applicative push (URL backend tenant, certificats, restrictions).

---

*Suite : [06 — Architecture IA](06_architecture_ia.md)*
