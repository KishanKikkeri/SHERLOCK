import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Ear, Volume2, VolumeX, Info, MessageSquare } from 'lucide-react'
import { useVoice } from './useVoice'
import { useAudioRecorder } from './useAudioRecorder'
import { Waveform } from './Waveform'
import { VUMeter } from './VUMeter'
import { useConversation } from '@/conversation/hooks/useConversation'
import { useConversationStore, type ChatMessage } from '@/conversation/store'
import { ConversationMessage } from '@/conversation/ConversationMessage'
import { AgentExecutionTimeline } from '@/conversation/AgentExecutionTimeline'
import { useVoiceCommandPhrases, useVoiceQuery } from '@/lib/queries/voice'
import { useSessions } from '@/lib/queries/sessions'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useLanguage } from '@/providers/LanguageProvider'

function newMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Priority 14-17 — Voice, rebuilt on the exact same conversation state
 * as the Conversation screen (`useConversationStore`, a zustand store —
 * already global, not React-context-scoped) instead of a parallel local
 * `turns` array. A question typed on /conversation and a follow-up
 * spoken here read the same session_id and the same message history:
 * "Show suspects" typed, then "Which one is most dangerous?" spoken,
 * resolves the pronoun correctly because it's literally the same
 * conversation, not two conversations compared after the fact.
 */
export function VoicePage() {
  const { language, t } = useLanguage()
  const [useServerAudio, setUseServerAudio] = useState(false)
  const [muted, setMuted] = useState(false)

  const { data: openSessions } = useSessions({ status: 'open' })
  const { data: phrases } = useVoiceCommandPhrases()
  const voiceQuery = useVoiceQuery()
  const recorder = useAudioRecorder()

  // Same hook the Conversation screen's ChatComposer/VoiceButton use —
  // same zustand store underneath, so sessionId/messages/timeline are
  // shared automatically regardless of which screen is mounted.
  const { messages, timeline, isStreaming, sessionId, sendMessage, setSessionId } = useConversation()
  const store = useConversationStore()

  // ── Path A: browser STT -> shared conversation pipeline ──────────
  const handleBrowserCommand = useCallback(
    (text: string) => {
      void sendMessage(text)
    },
    [sendMessage],
  )

  const wakePhraseList = phrases ? Object.values(phrases).map((p) => p.en) : undefined
  const voice = useVoice(handleBrowserCommand, language as 'en' | 'kn', wakePhraseList)

  // Priority 16 — speak the assistant's reply as soon as it's ready.
  // Guarded so each finished assistant message is only spoken once,
  // and reset per-turn so speakStream's "already spoken" cursor
  // doesn't bleed into the next answer.
  const lastSpokenIdRef = useRef<string | null>(null)
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  useEffect(() => {
    if (!lastAssistant || lastAssistant.pending || muted) return
    if (lastSpokenIdRef.current === lastAssistant.id) return
    lastSpokenIdRef.current = lastAssistant.id
    voice.actions.resetSpeakStream()
    voice.actions.speakStream(lastAssistant.text, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastAssistant?.id, lastAssistant?.pending, muted])

  const handleReplay = useCallback(
    (text: string) => {
      voice.actions.speak(text)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  // ── Path B: record -> POST /voice/query (Kannada fallback) ──────
  // Writes into the same shared store as Path A, so switching between
  // browser STT and server-side audio mid-session still reads as one
  // conversation, not two.
  async function handleStartRecording() {
    await recorder.start()
  }

  async function handleStopRecording() {
    const blob = await recorder.stop()
    const userId = newMessageId()
    const assistantId = newMessageId()
    store.addMessage({ id: userId, role: 'user', text: '(transcribing…)', pending: true, createdAt: new Date().toISOString() })
    store.addMessage({ id: assistantId, role: 'assistant', text: '', pending: true, createdAt: new Date().toISOString() })
    try {
      const result = await voiceQuery.mutateAsync({ audioBlob: blob, sessionId, languageHint: language })
      const spoken = language === 'en' ? result.spoken_response_en : result.spoken_response
      store.updateMessage(userId, { text: result.transcript || '(no speech detected)', pending: false })
      store.updateMessage(assistantId, { text: spoken, pending: false, intent: result.intent })
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
      store.updateMessage(userId, { pending: false, error: 'Transcription failed.', text: '(transcription failed)' })
      store.updateMessage(assistantId, { pending: false, error: 'Voice query failed — check the backend is reachable.', text: 'Voice query failed.' })
    }
  }

  const orderedMessages = messages

  return (
    <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">{t('navigation.voice', 'Voice')}</h1>
          <p className="text-xs text-muted">
            {sessionId
              ? `Attached to session #${sessionId} — same conversation as the Conversation screen`
              : 'No session attached — voice commands that need one will ask'}
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
            {voice.state.conversationActive && !voice.state.transcript && (
              <p className="text-xs text-muted">Listening — no need to say the wake word again yet</p>
            )}
            {voice.state.speaking && (
              <p className="text-xs text-accent">Speaking — say anything to interrupt</p>
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
                  isLoading={voiceQuery.isPending}
                >
                  {recorder.isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  {recorder.isRecording ? 'Stop & send' : 'Tap to record'}
                </Button>
              )}
            </div>

            {voice.state.error && <p className="text-xs text-critical">Voice error: {voice.state.error}</p>}

            <div className="flex items-center gap-3 border-t border-border pt-4">
              <Badge tone="neutral">
                {t('voice.language_label', 'Voice language')}: {language === 'kn' ? 'ಕನ್ನಡ' : 'English'}
              </Badge>
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
          <CardHeader title="Conversation" />
          <CardBody className="flex-1 overflow-y-auto">
            {messages.length === 0 ? (
              <EmptyState
                icon={<Mic className="h-6 w-6" />}
                title="Nothing yet"
                description='Say "Sherlock" or hold to talk — this is the same conversation as the Conversation screen.'
              />
            ) : (
              <div className="flex flex-col gap-4">
                {isStreaming && <AgentExecutionTimeline steps={timeline} />}
                {orderedMessages.map((m: ChatMessage) => (
                  <div key={m.id} className="group relative">
                    <ConversationMessage message={m} />
                    {m.role === 'assistant' && !m.pending && m.text && (
                      <button
                        type="button"
                        onClick={() => handleReplay(m.text)}
                        className="mt-1 flex items-center gap-1 text-xs text-muted hover:text-text"
                        title="Replay this response"
                      >
                        <MessageSquare className="h-3 w-3" /> Replay
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
