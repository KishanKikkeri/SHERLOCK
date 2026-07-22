import { useCallback, useState } from 'react'
import { Mic, MicOff, Ear, Volume2, VolumeX, Info } from 'lucide-react'
import { useVoice } from './useVoice'
import { useAudioRecorder } from './useAudioRecorder'
import { Waveform } from './Waveform'
import { VUMeter } from './VUMeter'
import { LanguageSelector } from './LanguageSelector'
import { VoiceTurnCard } from './VoiceTurnCard'
import { newTurnId, type VoiceConversationTurn } from './conversation-turn'
import { useVoiceCommand, useVoiceCommandPhrases, useVoiceQuery } from '@/lib/queries/voice'
import { useSessions } from '@/lib/queries/sessions'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export function VoicePage() {
  const [language, setLanguage] = useState('en')
  const [useServerAudio, setUseServerAudio] = useState(false)
  const [sessionId, setSessionId] = useState<number | undefined>(undefined)
  const [turns, setTurns] = useState<VoiceConversationTurn[]>([])
  const [muted, setMuted] = useState(false)

  const { data: openSessions } = useSessions({ status: 'open' })
  const { data: phrases } = useVoiceCommandPhrases()
  const voiceCommand = useVoiceCommand()
  const voiceQuery = useVoiceQuery()
  const recorder = useAudioRecorder()

  const addTurn = useCallback((turn: VoiceConversationTurn) => {
    setTurns((prev) => [turn, ...prev])
  }, [])

  const updateTurn = useCallback((id: string, patch: Partial<VoiceConversationTurn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)))
  }, [])

  // ── Path A: browser STT -> POST /voice/command ──────────────────
  const handleBrowserCommand = useCallback(
    async (text: string) => {
      const id = newTurnId()
      addTurn({ id, query: text, language: 'en', path: 'browser', timestamp: new Date().toISOString(), pending: true })
      try {
        const result = await voiceCommand.mutateAsync({ transcript: text, session_id: sessionId })
        updateTurn(id, {
          pending: false,
          intent: result.intent,
          spokenResponse: result.spoken_response,
          data: result.data,
        })
        if (result.session_id) setSessionId(result.session_id)
        if (!muted) voice.actions.speak(result.spoken_response)
      } catch {
        updateTurn(id, { pending: false, error: 'Command failed — check the backend is reachable.' })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, muted, addTurn, updateTurn],
  )

  const voice = useVoice(handleBrowserCommand)

  const handleReplay = useCallback(
    (text: string) => {
      voice.actions.speak(text)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  // ── Path B: record -> POST /voice/query (Kannada fallback) ──────
  const [pendingTurnId, setPendingTurnId] = useState<string | null>(null)

  async function handleStartRecording() {
    await recorder.start()
  }

  async function handleStopRecording() {
    const blob = await recorder.stop()
    const id = newTurnId()
    setPendingTurnId(id)
    addTurn({
      id,
      query: '(transcribing…)',
      language,
      path: 'server',
      timestamp: new Date().toISOString(),
      pending: true,
    })
    try {
      const result = await voiceQuery.mutateAsync({ audioBlob: blob, sessionId, languageHint: language })
      const spoken = language === 'en' ? result.spoken_response_en : result.spoken_response
      updateTurn(id, {
        query: result.transcript || '(no speech detected)',
        pending: false,
        intent: result.intent,
        spokenResponse: spoken,
        data: result.data,
      })
      if (result.session_id) setSessionId(result.session_id)
      if (!muted) {
        if (result.audio_base64 && result.audio_content_type) {
          const audio = new Audio(`data:${result.audio_content_type};base64,${result.audio_base64}`)
          audio.play().catch(() => {})
        } else {
          // No TTS provider configured server-side — degrade honestly to
          // browser TTS rather than silently saying nothing.
          voice.actions.speak(spoken)
        }
      }
    } catch {
      updateTurn(id, { pending: false, error: 'Voice query failed — check the backend is reachable.' })
    } finally {
      setPendingTurnId(null)
    }
  }

  return (
    <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Voice</h1>
          <p className="text-xs text-muted">
            {sessionId ? `Attached to session #${sessionId}` : 'No session attached — voice commands that need one will ask'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted">
            Session
            <select
              value={sessionId ?? ''}
              onChange={(e) => setSessionId(e.target.value ? Number(e.target.value) : undefined)}
              className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
            >
              <option value="">None</option>
              {openSessions?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.session_code}
                </option>
              ))}
            </select>
          </label>
          <Button variant="ghost" size="icon" onClick={() => setMuted((m) => !m)} aria-label={muted ? 'Unmute' : 'Mute'} title={muted ? 'Unmute responses' : 'Mute responses'}>
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_320px] gap-4">
        <Card className="flex flex-col">
          <CardBody className="flex flex-1 flex-col items-center justify-center gap-5">
            {!voice.state.supported && !useServerAudio && (
              <div className="flex max-w-sm flex-col items-center gap-2 text-center">
                <Info className="h-5 w-5 text-warning" />
                <p className="text-sm text-text">
                  This browser doesn't support in-browser speech recognition.
                </p>
                <p className="text-xs text-muted">
                  Switch to server-side speech below — it works in any browser and is the
                  recommended path for Kannada regardless.
                </p>
              </div>
            )}

            <Waveform getAnalyser={voice.actions.getAnalyser} active={voice.state.dictating || voice.state.wakeListening} className="w-full max-w-md" />
            <VUMeter level={voice.state.audioLevel} className="w-full max-w-md" />

            {voice.state.transcript && (
              <p className="max-w-md text-center text-sm text-text" aria-live="polite">
                "{voice.state.transcript}"
              </p>
            )}
            {recorder.isRecording && <p className="text-sm text-warning">Recording — tap again to stop and send</p>}

            <div className="flex items-center gap-3">
              {!useServerAudio ? (
                <>
                  <Button
                    variant={voice.state.wakeListening ? 'primary' : 'secondary'}
                    onClick={voice.actions.toggleWakeListening}
                    disabled={!voice.state.supported}
                  >
                    <Ear className="h-4 w-4" />
                    {voice.state.wakeListening ? 'Listening for "Sherlock"' : 'Wake word off'}
                  </Button>
                  <Button
                    variant={voice.state.dictating ? 'primary' : 'secondary'}
                    onPointerDown={voice.actions.startPushToTalk}
                    onPointerUp={voice.actions.stopPushToTalk}
                    onPointerLeave={() => voice.state.dictating && voice.actions.stopPushToTalk()}
                    disabled={!voice.state.supported}
                  >
                    <Mic className="h-4 w-4" /> Hold to talk
                  </Button>
                </>
              ) : (
                <Button
                  variant={recorder.isRecording ? 'primary' : 'secondary'}
                  size="lg"
                  onClick={recorder.isRecording ? handleStopRecording : handleStartRecording}
                  isLoading={voiceQuery.isPending && pendingTurnId !== null}
                >
                  {recorder.isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  {recorder.isRecording ? 'Stop & send' : 'Tap to record'}
                </Button>
              )}
            </div>

            {voice.state.error && <p className="text-xs text-critical">Voice error: {voice.state.error}</p>}

            <div className="flex items-center gap-3 border-t border-border pt-4">
              <LanguageSelector value={language} onChange={setLanguage} />
              <Button
                variant={useServerAudio ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setUseServerAudio((v) => !v)}
                title="Real audio round-trip via the server — recommended for Kannada"
              >
                Server-side speech
              </Button>
            </div>

            {phrases && (
              <div className="flex max-w-md flex-wrap justify-center gap-1.5">
                {Object.values(phrases)
                  .slice(0, 4)
                  .map((p, i) => (
                    <Badge key={i} tone="neutral">
                      "{language === 'kn' ? p.kn : p.en}"
                    </Badge>
                  ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card className="flex flex-col overflow-hidden">
          <CardHeader title="Conversation history" />
          <CardBody className="flex-1 overflow-y-auto">
            {turns.length === 0 ? (
              <EmptyState
                icon={<Mic className="h-6 w-6" />}
                title="Nothing yet"
                description="Say “Sherlock” or hold to talk, and your commands will show up here."
              />
            ) : (
              <div className="flex flex-col gap-2">
                {turns.map((turn) => (
                  <VoiceTurnCard key={turn.id} turn={turn} onReplay={handleReplay} />
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
