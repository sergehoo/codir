# Module Notifications & Rappels — Checklist livraison bêta

## Backend

- [x] **Modèles** : Notification (étendu), NotificationPreference, NotificationLog, TaskReminderLog
- [x] **Migration** : `apps/notifications/migrations/0002_preferences_logs_reminderlog.py`
- [x] **Services notifications** : `notify`, `send_task_assigned_notification`, `send_task_delegated_notification`, `send_user_task_reminder`, `send_manager_branch_summary`, `notify_task_due_soon`, `notify_task_overdue`, `should_send_notification`, `prevent_duplicate_reminder`
- [x] **Services action_plans étendus** : `assign_task`, `delegate_task`, `postpone_task`, `cancel_task`, `mark_task_overdue`, `get_user_open_tasks`, `get_manager_branch_tasks_summary`
- [x] **Signal action_plans** : `post_save ActionTask` → `send_task_assigned_notification`
- [x] **Celery tasks** : `send_notification_email`, `send_daily_task_reminders_task`, `send_manager_daily_summaries_task`, `detect_overdue_tasks_task`, `send_due_soon_alerts_task`
- [x] **Celery Beat** : 09h00 / 16h00 (rappels + résumé manager) · 08h00 (due soon) · chaque heure (overdue) · 15 min (meetings) · TZ Africa/Abidjan
- [x] **Templates email** : base, task_assigned, task_delegated, daily_user_reminder, manager_summary, task_due_soon, task_overdue, generic — HTML + texte
- [x] **Config SMTP** : `EMAIL_BACKEND/HOST/PORT/USER/PASSWORD/USE_TLS/USE_SSL` env-driven, `DEFAULT_FROM_EMAIL`, `FRONTEND_BASE_URL`
- [x] **`.env.example`** : exemple Hostinger SMTP renseigné
- [x] **DRF API** :
  - `GET /notifications/` (filtres unread/event/channel)
  - `POST /notifications/{id}/mark-read/`
  - `POST /notifications/mark-all-read/`
  - `GET /notifications/unread-count/`
  - `GET /notifications/summary/`
  - `GET /notifications/preferences/me/`
  - `PATCH /notifications/preferences/me/`
  - `POST /notifications/test-email/`
  - `GET /notifications/dashboard/summary/`
  - `POST /action-plans/tasks/{id}/assign/`
  - `POST /action-plans/tasks/{id}/delegate/`
  - `POST /action-plans/tasks/{id}/remind/`
  - `POST /action-plans/tasks/{id}/postpone/`
  - `POST /action-plans/tasks/{id}/cancel/`
- [x] **Permissions** : `IsAuthenticated` partout, `recipient=request.user` pour notifs, préférences scoppées « me ».
- [x] **Anti-doublons** : `UniqueConstraint(user, task, reminder_type, reminder_date, time_slot)`.

## Frontend (React + TailwindCSS Atelier)

- [x] `NotificationBell` (top-right Shell, badge unread, dropdown 5 derniers + mark all)
- [x] `NotificationsPage` étendue : filtres event/channel/unread + statuts email
- [x] `NotificationPreferencesPage` : canaux + événements + heures de silence + test email
- [x] `TaskReminderCard` (dashboard) : 4 KPI quotidiens
- [x] `ManagerSummaryWidget` (dashboard) : KPI manager + top tâches
- [x] Route `/notifications/preferences`
- [x] Types TS étendus : `priority`, `channel`, `status`, `action_url`, `metadata` …

## Tests

- [x] `apps/notifications/tests/test_services.py` :
  - assignation → notif TASK_ASSIGNED
  - délégation → notif old + new
  - anti-doublon rappel (slot identique bloque, slots différents passent)
  - préférences désactivées (event off, channel off)
  - détection overdue → status + notif
  - daily reminder → notif TASK_REMINDER
  - due_soon → notif TASK_DUE_SOON
  - manager_summary agrège correctement

## Configuration à faire en prod

1. **Mettre à jour `.env`** avec les vrais identifiants SMTP Hostinger :
   ```
   EMAIL_HOST=smtp.hostinger.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=notification@votredomaine.com
   EMAIL_HOST_PASSWORD=•••••
   EMAIL_USE_TLS=True
   DEFAULT_FROM_EMAIL=CODIR Executive <notification@votredomaine.com>
   FRONTEND_BASE_URL=https://app.codir.votredomaine.com
   CELERY_TIMEZONE=Africa/Abidjan
   ```

2. **Lancer la migration** :
   ```bash
   python manage.py migrate notifications
   ```

3. **Lancer Celery worker + beat** :
   ```bash
   celery -A config worker -l info -Q notifications,default
   celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler
   ```

4. **Sanity check** : depuis la page Préférences → bouton « Envoyer un email de test ».

5. **Pour activer SMS / WhatsApp** plus tard, brancher un provider (Twilio, etc.)
   dans `notifications/services.py` (les helpers `_send_*` à créer) — la table
   `NotificationLog` est déjà prête à enregistrer le transport.

## Limites connues (à itérer)

- Les rappels sont basés sur l'heure UTC convertie via `CELERY_TIMEZONE` ; vérifier
  la cohérence avec les serveurs de production.
- L'agrégation manager se fait à chaque appel (pas de cache). Si > 1000 tâches
  ouvertes, prévoir un cache Redis 5 min.
- Pas encore de gestion des « quiet hours » côté envoi email (préférences UI prêtes
  mais le worker ne filtre pas encore par heure du destinataire).
