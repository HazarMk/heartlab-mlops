import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ApiService,
  ResearchReadiness,
  ResearchReadinessItem,
  ResearchReadinessUpdate,
} from './api.service';
import { AuthService } from './auth.service';

@Component({
  standalone: true,
  imports: [FormsModule],
  template: `
    <section class="page-heading readiness-heading">
      <p class="eyebrow">CADRE DE RECHERCHE <span>/</span> TUNISIE</p>
      <h1>Préparer le projet,<br><em>étape par étape.</em></h1>
      <p>Cette checklist réunit les sujets à cadrer avec les équipes cliniques, scientifiques, éthiques, de protection des données et réglementaires avant une éventuelle recherche impliquant des patients.</p>
    </section>

    @if (error) {
      <div class="error-banner" role="alert">{{ error }}</div>
    } @else if (!readiness) {
      <div class="readiness-loading" role="status">Chargement de la checklist…</div>
    } @else {
      <section class="readiness-overview" aria-label="État général du projet">
        <article class="readiness-state">
          <div class="state-icon">R</div>
          <div class="state-copy"><small>STATUT DU PROJET</small><strong>Préparation de recherche</strong><span>Les éléments de la checklist restent à évaluer.</span></div>
          <span class="state-badge">Pas un dispositif clinique</span>
        </article>
        <article class="readiness-progress">
          <div class="progress-head"><span>Éléments documentés</span><strong>{{ readiness.completed_items }} / {{ readiness.total_items }}</strong></div>
          <div class="readiness-track" role="progressbar" [attr.aria-valuenow]="readiness.completed_items" [attr.aria-valuemin]="0" [attr.aria-valuemax]="readiness.total_items">
            <span [style.width.%]="progressPercent"></span>
          </div>
          <small>« Documenté » signifie déclaré par l’équipe, pas vérifié, approuvé ou autorisé pour un usage clinique.</small>
        </article>
      </section>

      <section class="readiness-warning" role="note">
        <span class="warning-mark">!</span>
        <div><strong>Le modèle actuel reste une démonstration</strong><p>Il n’a pas été validé cliniquement. N’utilise pas de données réelles de patients et ne l’emploie pas pour un diagnostic ou une décision de soin.</p></div>
      </section>
      @if (!auth.canEditResearch()) {
        <aside class="read-only-notice">Mode lecture : un administrateur doit autoriser la modification du suivi.</aside>
      }

      <section class="readiness-list">
        <div class="readiness-list-heading"><div><p class="eyebrow">POINTS À CADRER</p><h2>Ce qui doit être préparé</h2></div><span>{{ readiness.total_items }} sujets</span></div>
        <div class="readiness-grid">
          @for (item of readiness.items; track item.id; let index = $index) {
            <article class="readiness-card">
              <div class="readiness-card-top"><span class="readiness-number">POINT {{ (index + 1).toString().padStart(2, '0') }}</span><span class="readiness-status" [class.status-complete]="item.status === 'complete'" [class.status-blocked]="item.status === 'blocked'">{{ statusLabel(item.status) }}</span></div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
              <div class="evidence-block"><small>PREUVE À PRÉPARER</small><span>{{ item.evidence }}</span></div>
              <div class="readiness-fields">
                <label>Statut
                  <select [(ngModel)]="drafts[item.id].status" [name]="'status-' + item.id" [disabled]="!auth.canEditResearch()">
                    <option value="not_started">À préparer</option>
                    <option value="in_progress">En cours</option>
                    <option value="blocked">Bloqué</option>
                    <option value="complete">Documenté</option>
                  </select>
                </label>
                <label>Responsable
                  <input [(ngModel)]="drafts[item.id].owner" [name]="'owner-' + item.id" maxlength="100" placeholder="Nom ou rôle" [disabled]="!auth.canEditResearch()">
                </label>
                <label>Échéance
                  <input type="date" [(ngModel)]="drafts[item.id].due_date" [name]="'date-' + item.id" [disabled]="!auth.canEditResearch()">
                </label>
                <label class="notes-field">Note de suivi
                  <textarea [(ngModel)]="drafts[item.id].notes" [name]="'notes-' + item.id" maxlength="2000" rows="2" placeholder="Action, décision ou référence documentaire — sans données de patient" [disabled]="!auth.canEditResearch()"></textarea>
                </label>
              </div>
              <div class="readiness-card-footer">
                <span>{{ item.updated_at ? 'Mis à jour ' + formatUpdated(item.updated_at) : 'Pas encore mis à jour' }}{{ item.updated_by ? ' · ' + item.updated_by : '' }}</span>
                @if (auth.canEditResearch()) {
                  <button type="button" (click)="save(item)" [disabled]="saving[item.id]">
                  {{ saving[item.id] ? 'Enregistrement…' : savedItem === item.id ? 'Enregistré ✓' : 'Enregistrer' }}
                  </button>
                }
              </div>
              @if (item.history.length) {
                <details class="audit-history">
                  <summary>Historique récent · {{ item.history.length }}</summary>
                  @for (event of item.history; track $index) {
                    <div class="audit-event"><span>{{ formatUpdated(event.updated_at) }} · {{ event.updated_by }}</span><small>{{ fieldLabels(event.changed_fields) }}</small></div>
                  }
                </details>
              }
              @if (itemErrors[item.id]) { <div class="item-error" role="alert">{{ itemErrors[item.id] }}</div> }
            </article>
          }
        </div>
      </section>

      <p class="readiness-disclaimer">{{ readiness.disclaimer }}</p>
    }
  `,
})
export class ResearchReadinessComponent {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly auth = inject(AuthService);
  readiness: ResearchReadiness | null = null;
  error = '';
  drafts: Record<string, ResearchReadinessUpdate> = {};
  saving: Record<string, boolean> = {};
  itemErrors: Record<string, string> = {};
  savedItem: string | null = null;

  constructor() {
    this.api.researchReadiness().subscribe({
      next: value => {
        this.readiness = value;
        this.drafts = Object.fromEntries(value.items.map(item => [item.id, {
          status: item.status,
          owner: item.owner ?? '',
          due_date: item.due_date ?? '',
          notes: item.notes ?? '',
        }]));
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'La checklist est indisponible. Vérifie que l’API fonctionne et que ta session est active.';
        this.cdr.markForCheck();
      },
    });
  }

  get progressPercent(): number {
    if (!this.readiness || this.readiness.total_items === 0) return 0;
    return (this.readiness.completed_items / this.readiness.total_items) * 100;
  }

  statusLabel(status: string): string {
    if (status === 'complete') return 'Documenté';
    if (status === 'in_progress') return 'En cours';
    if (status === 'blocked') return 'Bloqué';
    return 'À préparer';
  }

  formatUpdated(value: string): string {
    return new Date(value).toLocaleString('fr-FR', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  }

  fieldLabels(fields: string[]): string {
    const labels: Record<string, string> = {
      status: 'statut',
      owner: 'responsable',
      due_date: 'échéance',
      notes: 'note',
    };
    return fields.map(field => labels[field] ?? field).join(', ');
  }

  save(item: ResearchReadinessItem): void {
    const draft = this.drafts[item.id];
    if (!draft) return;

    this.saving[item.id] = true;
    this.savedItem = null;
    delete this.itemErrors[item.id];

    const update: ResearchReadinessUpdate = {
      status: draft.status,
      owner: draft.owner?.trim() || null,
      due_date: draft.due_date || null,
      notes: draft.notes?.trim() || null,
    };

    this.api.updateResearchReadinessItem(item.id, update).subscribe({
      next: () => {
        this.savedItem = item.id;
        this.saving[item.id] = false;
        this.refresh();
      },
      error: () => {
        this.itemErrors[item.id] = 'Enregistrement impossible. Réessaie et vérifie que ta session est active.';
        this.saving[item.id] = false;
        this.cdr.markForCheck();
      },
    });
  }

  private refresh(): void {
    this.api.researchReadiness().subscribe({
      next: value => {
        this.readiness = value;
        this.drafts = Object.fromEntries(value.items.map(item => [item.id, {
          status: item.status,
          owner: item.owner ?? '',
          due_date: item.due_date ?? '',
          notes: item.notes ?? '',
        }]));
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Mise à jour enregistrée, mais le tableau de bord ne peut pas être actualisé.';
        this.cdr.markForCheck();
      },
    });
  }
}
