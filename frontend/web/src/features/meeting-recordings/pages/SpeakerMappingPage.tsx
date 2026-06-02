// Page d'identification des voix — route /meetings/$meetingId/recordings/$recordingId/speakers
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, Mic } from 'lucide-react'
import { useMemo } from 'react'

import { meetingsApi } from '@/features/meetings/api'

import { SpeakerIdentificationPanel } from '../components/SpeakerIdentificationPanel'
import { useRecordingDetail } from '../hooks/useRecordingExtraction'

export function SpeakerMappingPage() {
  const params = useParams({ strict: false }) as { meetingId: string; recordingId: string }
  const { meetingId, recordingId } = params
  const navigate = useNavigate()

  const meetingQuery = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => meetingsApi.retrieve(meetingId),
  })
  const participantsQuery = useQuery({
    queryKey: ['meeting', meetingId, 'participants'],
    queryFn: () => meetingsApi.listParticipants(meetingId),
  })
  const recordingQuery = useRecordingDetail(recordingId)

  const participants = useMemo(() => {
    const list = participantsQuery.data ?? []
    return list
      .filter((p: any) => p.user)
      .map((p: any) => ({
        id: p.user.id,
        full_name: p.user.full_name
          || `${p.user.first_name ?? ''} ${p.user.last_name ?? ''}`.trim()
          || p.user.email,
        email: p.user.email,
        role: p.role,
      }))
  }, [participantsQuery.data])

  const onConfirmed = () => {
    navigate({
      to: '/meetings/$meetingId/recordings/$recordingId/summary',
      params: { meetingId, recordingId },
    })
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Link
          to="/meetings/$id"
          params={{ id: meetingId }}
          className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg transition"
        >
          <ChevronLeft size={14} /> Retour à la réunion
        </Link>
      </div>

      <div>
        <h1 className="serif text-2xl font-semibold flex items-center gap-2">
          <Mic size={20} className="text-copper-500" />
          Identifier les voix détectées
        </h1>
        <p className="text-sm text-fg-muted mt-1">
          {meetingQuery.data?.title}
        </p>
      </div>

      {recordingQuery.isLoading || participantsQuery.isLoading ? (
        <div className="p-8 text-center text-sm text-fg-muted">Chargement…</div>
      ) : (
        <SpeakerIdentificationPanel
          recordingId={recordingId}
          participants={participants}
          onConfirmed={onConfirmed}
        />
      )}
    </div>
  )
}
