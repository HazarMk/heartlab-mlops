import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { ApiService, Health } from './api.service';

function metric(text: string, name: string): number | null {
  const values = text.split(/\r?\n/).filter(line => line.startsWith(name)).map(line => Number(line.trim().split(/\s+/).at(-1))).filter(Number.isFinite);
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
}

@Component({
  standalone: true,
  template: `
    <section class="page-heading"><p class="eyebrow">OBSERVABILITÉ DE LA DÉMO</p><h1>Monitoring du service</h1><p>Indicateurs techniques et métriques expérimentales de FastAPI et Prometheus ; ils ne décrivent pas la santé de personnes.</p></section>
    @if (error) { <div class="error-banner">{{ error }}</div> }
    <section class="monitor-grid">
      <article><small>API</small><strong>{{ health?.status || 'Indisponible' }}</strong><span>État du service</span></article>
      <article><small>PRÉDICTIONS</small><strong>{{ predictions ?? '—' }}</strong><span>Compteur Prometheus</span></article>
      <article><small>ERREURS</small><strong>{{ errors ?? '—' }}</strong><span>Erreurs de prédiction</span></article>
      <article><small>LIGNES ÉVALUÉES</small><strong>{{ evaluated ?? '—' }}</strong><span>Lignes avec étiquettes de démonstration</span></article>
    </section>
    <section class="monitor-grid quality">
      <article><small>DERNIÈRE EXACTITUDE</small><strong>{{ pct(accuracy) }}</strong></article>
      <article><small>DERNIÈRE PRÉCISION</small><strong>{{ pct(precision) }}</strong></article>
      <article><small>DERNIER RAPPEL</small><strong>{{ pct(recall) }}</strong></article>
    </section>
    <p class="muted">Les métriques de qualité sont expérimentales et apparaissent après l'évaluation d'un lot de démonstration étiqueté.</p>
    <button class="secondary-button" (click)="refresh()">Actualiser les indicateurs</button>
  `,
})
export class MonitoringComponent {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  health: Health | null = null; predictions: number | null = null; errors: number | null = null; evaluated: number | null = null;
  accuracy: number | null = null; precision: number | null = null; recall: number | null = null; error = '';
  constructor() { this.refresh(); }
  pct(value: number | null): string { return value === null ? '—' : `${(value * 100).toFixed(1)}%`; }
  refresh(): void {
    this.error = '';
    this.api.health().subscribe({ next: value => { this.health = value; this.cdr.markForCheck(); }, error: () => { this.error = "API inaccessible. Démarre FastAPI sur le port 8001."; this.cdr.markForCheck(); } });
    this.api.metrics().subscribe({ next: text => {
      this.predictions = metric(text, 'predictions_total'); this.errors = metric(text, 'prediction_errors_total'); this.evaluated = metric(text, 'model_evaluation_rows_total');
      this.accuracy = metric(text, 'model_accuracy'); this.precision = metric(text, 'model_precision'); this.recall = metric(text, 'model_recall');
      this.cdr.markForCheck();
    }, error: () => { this.error = "Les métriques Prometheus sont indisponibles."; this.cdr.markForCheck(); } });
  }
}
