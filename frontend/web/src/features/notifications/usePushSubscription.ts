/**
 * usePushSubscription — Lot 6 : hook qui gère l'abonnement Web Push.
 *
 * Workflow :
 *   1. Register le service worker `/sw.js` (idempotent — appelable plusieurs fois).
 *   2. Récupère la clé publique VAPID depuis le backend.
 *   3. À la demande utilisateur (clic "Activer") :
 *      - Demande la permission Notification.
 *      - Appelle PushManager.subscribe() avec la clé VAPID.
 *      - POST l'endpoint + keys au backend (/notifications/push/subscribe/).
 *   4. À la désactivation : unsubscribe() + POST /push/unsubscribe/.
 *
 * État retourné :
 *   - `supported` : true si Push + ServiceWorker + Notification dispos
 *   - `permission` : 'default' | 'granted' | 'denied'
 *   - `subscribed` : true si abonnement actif
 *   - `enable()` / `disable()` : actions
 *   - `loading` / `error`
 */
import { useCallback, useEffect, useState } from 'react'

import { apiClient } from '@/api/client'


function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
  )
}


/** Convertit la clé VAPID base64-url en Uint8Array (format attendu par subscribe). */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i)
  return out
}


export function usePushSubscription() {
  const supported = isPushSupported()
  const [permission, setPermission] = useState<NotificationPermission>(
    supported ? Notification.permission : 'denied',
  )
  const [subscribed, setSubscribed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Au mount : enregistre le SW + vérifie si déjà abonné
  useEffect(() => {
    if (!supported) return
    let alive = true

    async function init() {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js')
        // Vérifie l'abonnement existant
        const sub = await reg.pushManager.getSubscription()
        if (alive) setSubscribed(!!sub)
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
    }
    init()
    return () => { alive = false }
  }, [supported])

  // Au focus de la fenêtre : re-check permission (l'utilisateur peut l'avoir
  // changée depuis les settings navigateur).
  useEffect(() => {
    if (!supported) return
    const onFocus = () => setPermission(Notification.permission)
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [supported])

  // Écoute les messages du SW pour la navigation (clic sur notif)
  useEffect(() => {
    if (!supported) return
    const onMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'navigate' && typeof e.data.url === 'string') {
        // Tanstack router navigation se fait par hash/path direct
        window.location.href = e.data.url
      }
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [supported])

  const enable = useCallback(async () => {
    if (!supported) {
      setError("Votre navigateur ne supporte pas les notifications push.")
      return
    }
    setLoading(true); setError(null)
    try {
      // 1. Permission
      const perm = await Notification.requestPermission()
      setPermission(perm)
      if (perm !== 'granted') {
        throw new Error("Permission refusée. Vérifiez vos paramètres navigateur.")
      }

      // 2. Clé VAPID publique
      const r = await apiClient.get<{ key: string }>(
        '/notifications/push/vapid-public-key/',
      )
      const vapidKey = r.data.key
      if (!vapidKey) {
        throw new Error(
          "Push non configuré côté serveur. Contactez votre administrateur "
          + "pour activer VAPID."
        )
      }

      // 3. Subscribe via PushManager
      const reg = await navigator.serviceWorker.ready
      // Cast : TS strict considère Uint8Array<ArrayBufferLike> incompatible
      // avec BufferSource, mais c'est runtime-OK. applicationServerKey accepte
      // bien Uint8Array (spec Push API).
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey) as BufferSource,
      })

      // 4. POST au backend
      const json = sub.toJSON()
      await apiClient.post('/notifications/push/subscribe/', {
        endpoint: json.endpoint,
        keys: json.keys,
      })
      setSubscribed(true)
    } catch (e) {
      setError((e as Error).message || 'Erreur inconnue')
      throw e
    } finally {
      setLoading(false)
    }
  }, [supported])

  const disable = useCallback(async () => {
    if (!supported) return
    setLoading(true); setError(null)
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) {
        const endpoint = sub.endpoint
        await sub.unsubscribe()
        try {
          await apiClient.post('/notifications/push/unsubscribe/', { endpoint })
        } catch { /* non bloquant côté UX */ }
      }
      setSubscribed(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [supported])

  return { supported, permission, subscribed, loading, error, enable, disable }
}
