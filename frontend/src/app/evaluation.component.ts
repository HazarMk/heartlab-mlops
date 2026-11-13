import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { ApiService, Evaluation, Patient } from './api.service';

const FEATURES = ['age','sex','cp','trestbps','chol','fbs','restecg','thalach','exang','oldpeak','slope','ca','thal'];

@Component({
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page-heading"><p class="eyebrow">ÉVALUATION EXPÉRIMENTALE</p><h1>Qualité du modèle</h1><p>Mesure des métriques sur un jeu de démonstration étiqueté ; ce résultat ne valide pas un usage médical.</p></section>
    <section class="upload-card"><div class="upload-intro"><span class="upload-number">01</span><div><h2>Importer un CSV de démonstration</h2><p>Utilise uniquement un fichier fictif avec les 13 variables Cleveland et la colonne <code>target</code> (0 ou 1).</p></div></div>
      <label class="file-drop"> <input type="file" accept=".csv,text/csv" (change)="choose($event)"><strong>{{ fileName || 'Choisir un fichier CSV' }}</strong><span>N’importe pas de données réelles, personnelles ou de santé.</span></label>
      @if (error) { <div class="error-banner">{{ error }}</div> }
      <button class="action-button" [disabled]="!rows.length || loading" (click)="evaluate()">{{ loading ? 'Calcul en cours…' : 'Calculer les métriques →' }}</button>
    </section>
    @if (result) { <section class="quality-grid"><article><small>EXACTITUDE EXPÉRIMENTALE</small><strong>{{ result.accuracy | percent:'1.1-1' }}</strong></article><article><small>PRÉCISION EXPÉRIMENTALE</small><strong>{{ result.precision | percent:'1.1-1' }}</strong></article><article><small>RAPPEL EXPÉRIMENTAL</small><strong>{{ result.recall | percent:'1.1-1' }}</strong></article><p>Calculées sur {{ result.rows }} lignes du jeu importé. Ces métriques ne prouvent pas la validité clinique du modèle.</p></section> }
  `,
})
export class EvaluationComponent {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  fileName = ''; rows: Patient[] = []; labels: number[] = [];
  result: Evaluation | null = null; loading = false; error = '';

  async choose(event: Event): Promise<void> {
    const file = (event.target as HTMLInputElement).files?.[0];
    this.error = ''; this.rows = []; this.labels = []; this.result = null;
    if (!file) return;
    this.fileName = file.name;
    try {
      const lines = (await file.text()).trim().split(/\r?\n/);
      const headers = lines.shift()?.split(',').map(x => x.trim()) ?? [];
      if (![...FEATURES, 'target'].every(name => headers.includes(name))) throw new Error('Colonnes requises absentes : ' + [...FEATURES, 'target'].filter(name => !headers.includes(name)).join(', '));
      for (const line of lines) {
        const values = line.split(',');
        const record: Record<string, number | null> = {};
        headers.forEach((name, i) => { record[name] = values[i]?.trim() === '' || values[i]?.trim() === '?' ? null : Number(values[i]); });
        const target = record['target'];
        if (target !== 0 && target !== 1) throw new Error('La colonne target doit contenir uniquement 0 ou 1.');
        this.labels.push(target);
        const patient = Object.fromEntries(FEATURES.map(name => [name, record[name] ?? null])) as unknown as Patient;
        this.rows.push(patient);
      }
      if (!this.rows.length) throw new Error('Le fichier est vide.');
    } catch (err) { this.error = err instanceof Error ? err.message : 'Lecture du fichier impossible.'; }
    this.cdr.markForCheck();
  }

  evaluate(): void {
    this.loading = true; this.error = '';
    this.api.evaluate(this.rows, this.labels).subscribe({
      next: value => { this.result = value; this.loading = false; this.cdr.markForCheck(); },
      error: () => { this.error = "L'évaluation a échoué. Vérifie l'API et le format du CSV."; this.loading = false; this.cdr.markForCheck(); },
    });
  }
}
