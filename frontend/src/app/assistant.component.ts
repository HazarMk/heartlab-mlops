import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, AssistantReply, AssistantStatus, AssistantSource } from './api.service';

interface Message { role: 'user' | 'assistant'; text: string; sources?: AssistantSource[]; mode?: string; notice?: string | null; }

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="assistant-page">
      <header class="assistant-heading">
        <div><p class="eyebrow">HEARTLAB · INFORMATION SANTÉ</p><h1>Assistant santé</h1>
          <p>Posez votre question en français, en anglais ou en arabe. La réponse suit la langue de votre message.</p></div>
        <span class="assistant-mode" [class.mode-llm]="status?.llm_enabled">{{ status?.provider === 'huggingface_local' ? (status?.model_ready ? 'Qwen local prêt' : 'Qwen local en chargement') : status?.llm_enabled ? 'LLM disponible' : 'RAG local disponible' }}</span>
      </header>

      <aside class="assistant-notice" role="note">
        <strong>Information importante</strong>
        <p>Cet assistant ne pose pas de diagnostic et ne remplace pas un médecin. N’écrivez aucun nom, numéro CNAM, téléphone ou détail médical personnel. En cas d’urgence, contactez les services d’urgence locaux.</p>
      </aside>

      <section class="assistant-chat" aria-label="Conversation avec l’assistant">
        @if (messages.length === 0) {
          <div class="assistant-empty"><span>✦</span><h2>Comment puis-je vous aider ?</h2><p>Français : « Comment demander un rendez-vous ? »<br>English: “How do I request an appointment?”<br lang="ar" dir="rtl">العربية: « كيف أطلب موعداً؟ »</p></div>
        }
        @for (message of messages; track $index) {
          <article class="assistant-message" [class.from-user]="message.role === 'user'" [attr.dir]="isArabic(message.text) ? 'rtl' : 'ltr'">
            <span class="message-role">{{ message.role === 'user' ? 'Vous' : 'Assistant HeartLab' }}</span>
            <p>{{ message.text }}</p>
            @if (message.sources?.length) {
              <div class="answer-sources"><strong>Sources utilisées</strong>
                @for (source of message.sources; track source.id) {
                  <a [href]="source.url || null" [attr.target]="source.url ? '_blank' : null" [attr.rel]="source.url ? 'noopener noreferrer' : null">{{ source.title }} <small>— {{ source.source }}</small></a>
                }
              </div>
            }
            @if (message.notice) { <small class="answer-fallback-note">{{ message.notice }}</small> }
            @if (message.mode) { <small class="answer-mode">Mode : {{ message.mode === 'rag_llm' ? 'RAG + LLM' : message.mode === 'rag_fallback' ? 'RAG local (réponse rapide)' : message.mode === 'rag_no_match' ? 'aucune source correspondante' : 'RAG local' }}</small> }
          </article>
        }
        @if (loading) { <div class="assistant-loading" role="status"><span class="assistant-spinner"></span><span>Recherche dans les sources…</span></div> }
        @if (error) { <p class="assistant-error" role="alert">{{ error }}</p> }
      </section>

      <form class="assistant-composer" (ngSubmit)="send()">
        <label for="assistant-question">Votre question</label>
        <textarea id="assistant-question" name="question" [(ngModel)]="question" [attr.dir]="isArabic(question) ? 'rtl' : 'ltr'" maxlength="1200" rows="3" required placeholder="Écrivez une question générale…"></textarea>
        <div class="assistant-consent">
          <input id="use-llm" type="checkbox" name="useLlm" [(ngModel)]="useLlm" [disabled]="!status?.llm_enabled" />
          <label for="use-llm">{{ status?.provider === 'huggingface_local' ? 'Utiliser Qwen sur cette machine ; la question reste locale.' : 'Autoriser l’envoi de cette question au service OpenAI externe.' }}</label>
        </div>
        <div class="composer-footer"><small>{{ question.length }}/1200 · Sans cette option, la réponse reste locale et fondée sur les documents affichés.</small>
          <button type="submit" [disabled]="loading || !question.trim()">{{ loading ? 'Recherche…' : 'Envoyer la question' }} <span aria-hidden="true">→</span></button>
        </div>
      </form>
    </section>
  `,
})
export class AssistantComponent {
  private readonly api = inject(ApiService);
  status: AssistantStatus | null = null;
  messages: Message[] = [];
  question = '';
  useLlm = false;
  loading = false;
  error = '';
  private statusTimer?: number;

  isArabic(text: string): boolean { return /[\u0600-\u06ff]/.test(text); }

  constructor() {
    this.refreshStatus();
  }

  private refreshStatus(): void {
    this.api.assistantStatus().subscribe({
      next: status => {
        this.status = status;
        if (status.model_ready && this.statusTimer !== undefined) {
          window.clearInterval(this.statusTimer);
          this.statusTimer = undefined;
        } else if (status.provider === 'huggingface_local' && this.statusTimer === undefined) {
          this.statusTimer = window.setInterval(() => this.refreshStatus(), 5000);
        }
      },
      error: () => this.error = 'Le statut de l’assistant est indisponible.',
    });
  }

  ngOnDestroy(): void {
    if (this.statusTimer !== undefined) window.clearInterval(this.statusTimer);
  }

  send(): void {
    const text = this.question.trim();
    if (!text || this.loading) return;
    this.messages.push({ role: 'user', text });
    this.question = '';
    this.loading = true;
    this.error = '';
    this.api.askAssistant(text, this.useLlm).subscribe({
      next: (reply: AssistantReply) => {
        this.messages.push({ role: 'assistant', text: reply.answer, sources: reply.sources, mode: reply.mode, notice: reply.notice });
        this.loading = false;
      },
      error: () => {
        this.error = 'La réponse prend trop de temps. Réessayez ; si le mode IA est activé, désactivez-le pour utiliser le RAG local.';
        this.loading = false;
      },
    });
  }
}
