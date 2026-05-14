import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  ArrowUpRight, FileText, Lock, Trash2, Upload,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/widgets/EmptyState'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'

import { documentsApi, documentsKeys, formatBytes, type DocumentItem } from './api'

export function DocumentsPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: documentsKeys.list(),
    queryFn: () => documentsApi.list(),
  })
  const docs = (Array.isArray(data) ? data : (data?.results ?? [])) as DocumentItem[]

  const fileRef = useRef<HTMLInputElement>(null)
  const [confidential, setConfidential] = useState(false)
  const [uploadingName, setUploadingName] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => documentsApi.upload(file, confidential),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: documentsKeys.all })
      toast.success('Document importé')
      setUploadingName(null)
    },
    onError: () => { toast.error('Échec import'); setUploadingName(null) },
  })

  const remove = useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: documentsKeys.all }); toast.success('Document supprimé') },
  })

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setUploadingName(f.name)
    upload.mutate(f)
    e.target.value = ''
  }

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Référentiel"
        title="Documents"
        description={`${docs.length} fichier(s) dans le tenant`}
        actions={
          <>
            <label className="flex items-center gap-2 text-sm cursor-pointer text-fg-muted">
              <input type="checkbox" className="accent-copper-500"
                     checked={confidential} onChange={(e) => setConfidential(e.target.checked)} />
              Confidentiel
            </label>
            <PremiumButton iconLeft={<Upload size={15} />}
                           loading={upload.isPending}
                           onClick={() => fileRef.current?.click()}>
              Importer
            </PremiumButton>
            <input ref={fileRef} type="file" hidden onChange={handleFile} />
          </>
        }
      />

      <section className="px-10 py-8">
        {isLoading && <SkeletonList rows={4} />}

        {uploadingName && (
          <div className="card p-4 mb-3 flex items-center gap-3 animate-fade-in">
            <Upload size={16} className="text-copper-400 animate-soft-pulse" />
            <span className="text-sm">Import en cours…</span>
            <span className="text-2xs text-fg-subtle ml-auto truncate">{uploadingName}</span>
          </div>
        )}

        {!isLoading && docs.length === 0 && !uploadingName && (
          <EmptyState
            icon={FileText}
            title="Aucun document."
            description="Importez vos premiers fichiers — PV, contrats, pièces jointes, présentations."
            action={
              <PremiumButton iconLeft={<Upload size={15} />} onClick={() => fileRef.current?.click()}>
                Importer un document
              </PremiumButton>
            }
          />
        )}

        <div className="card overflow-hidden">
          {docs.length > 0 && (
            <table className="w-full text-left">
              <thead className="text-2xs uppercase tracking-widest text-fg-muted border-b border-border bg-bg-subtle/50">
                <tr>
                  <th className="py-3 px-5 font-semibold w-10">#</th>
                  <th className="py-3 px-5 font-semibold">Nom</th>
                  <th className="py-3 px-5 font-semibold">Type</th>
                  <th className="py-3 px-5 font-semibold">Taille</th>
                  <th className="py-3 px-5 font-semibold">Importé</th>
                  <th className="py-3 px-5"></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d, i) => (
                  <tr key={d.id} className="border-b border-border last:border-0 hover:bg-fg/[0.02] group">
                    <td className="py-4 px-5 text-fg-subtle font-mono text-2xs tabular">
                      {(i + 1).toString().padStart(2, '0')}
                    </td>
                    <td className="py-4 px-5">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <FileText size={14} strokeWidth={1.75} className="text-fg-subtle" />
                        <span className="truncate">{d.name}</span>
                        {d.is_confidential && (
                          <span className="inline-flex items-center text-warning text-2xs ml-2">
                            <Lock size={10} /> confidentiel
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-5 text-2xs uppercase tracking-wider text-fg-muted font-mono">
                      {d.mime?.split('/').pop() ?? '—'}
                    </td>
                    <td className="py-4 px-5 text-sm tabular text-fg-muted">{formatBytes(d.size_bytes)}</td>
                    <td className="py-4 px-5 text-2xs uppercase tracking-wider text-fg-subtle">
                      {format(new Date(d.created_at), "d MMM 'à' HH:mm", { locale: fr })}
                    </td>
                    <td className="py-4 px-5 text-right">
                      <div className="inline-flex items-center gap-3 opacity-0 group-hover:opacity-100 transition">
                        {d.download_url && (
                          <a href={d.download_url} target="_blank" rel="noreferrer"
                             className="text-copper-400 hover:underline text-2xs uppercase tracking-wider inline-flex items-center gap-1">
                            Ouvrir <ArrowUpRight size={11} />
                          </a>
                        )}
                        <button onClick={() => remove.mutate(d.id)}
                                className="text-fg-subtle hover:text-danger">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}
