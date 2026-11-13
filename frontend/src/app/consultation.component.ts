import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ApiService, Health, Patient, Prediction } from './api.service';

@Component({
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">ESPACE RECHERCHE <span> / </span> HEART LAB</p>
        <h1>Évaluer un modèle<br><em>en environnement isolé.</em></h1>
        <p class="hero-description">Explorez le modèle uniquement avec des profils fictifs. Cet espace reste séparé des parcours patient et médecin.</p>
        <div class="prototype-note"><b>Recherche uniquement</b><span>N’entrez aucune donnée personnelle ou réelle. Ce modèle n’est pas validé pour guider des soins.</span></div>
      </div>
      <div class="hero-visual"><img src="/heart-attack-concept.jpg" alt="Illustration du projet Heart Lab"><span>RECHERCHE · DONNÉES FICTIVES</span></div>
    </section>

    <section class="status-grid" aria-label="État du système">
      <article class="status-card"><span class="status-label">API SERVICE</span><strong>{{ health?.status === 'ok' ? 'Opérationnel' : 'En attente' }}</strong><small><i [class.online]="health?.status === 'ok'"></i> FastAPI · port 8001</small></article>
      <article class="status-card"><span class="status-label">CHAMPION</span><strong>{{ health?.model_loaded ? 'Modèle chargé' : 'Non disponible' }}</strong><small>MLflow · version {{ health?.model_version || '—' }}</small></article>
      <article class="status-card"><span class="status-label">SEUIL DE DÉCISION</span><strong>{{ health?.decision_threshold !== undefined ? (health?.decision_threshold | number:'1.3-3') : '—' }}</strong><small>Paramètre enregistré du modèle</small></article>
    </section>
    @if (apiError) { <div class="error-banner">API inaccessible. Démarre FastAPI sur le port 8001 et actualise cette page.</div> }

    <section class="workspace">
      <div class="section-heading"><div><p class="eyebrow">SIMULATION DE RECHERCHE</p><h2>Profil synthétique</h2><p>Variables fictives inspirées du jeu de données historique Cleveland.</p></div><span class="step-tag">RECHERCHE</span></div>
      <form [formGroup]="form" (ngSubmit)="submit()">
        <div class="form-section"><div class="form-title"><span>01</span><div><h3>Profil & variables</h3><p>Variables présentes dans le jeu de démonstration</p></div></div>
          <div class="fields three">
            <label>Âge <small>années</small><input type="number" formControlName="age"></label>
            <label>Sexe enregistré<select formControlName="sex"><option [ngValue]="0">Femme</option><option [ngValue]="1">Homme</option></select></label>
            <label>Douleur thoracique<select formControlName="cp"><option [ngValue]="1">Angine typique</option><option [ngValue]="2">Angine atypique</option><option [ngValue]="3">Douleur non angineuse</option><option [ngValue]="4">Asymptomatique</option></select></label>
          </div>
        </div>
        <div class="form-section"><div class="form-title"><span>02</span><div><h3>Mesures au repos</h3><p>Paramètres de base disponibles dans le dataset</p></div></div>
          <div class="fields three">
            <label>Pression artérielle <small>mmHg</small><input type="number" formControlName="trestbps"></label>
            <label>Cholestérol sérique <small>mg/dL</small><input type="number" formControlName="chol"></label>
            <label>Glycémie à jeun &gt; 120 mg/dL<select formControlName="fbs"><option [ngValue]="0">Non</option><option [ngValue]="1">Oui</option></select></label>
          </div>
        </div>
        <div class="form-section"><div class="form-title"><span>03</span><div><h3>Effort & examens</h3><p>Observations et examens complémentaires</p></div></div>
          <div class="fields three">
            <label>ECG au repos<select formControlName="restecg"><option [ngValue]="0">Normal</option><option [ngValue]="1">Anomalie ST-T</option><option [ngValue]="2">Hypertrophie ventriculaire gauche</option></select></label>
            <label>Fréquence cardiaque max <small>bpm</small><input type="number" formControlName="thalach"></label>
            <label>Angine à l'effort<select formControlName="exang"><option [ngValue]="0">Non</option><option [ngValue]="1">Oui</option></select></label>
            <label>Dépression ST à l'effort <small>oldpeak</small><input type="number" step="0.1" formControlName="oldpeak"></label>
            <label>Pente du segment ST<select formControlName="slope"><option [ngValue]="1">Montante</option><option [ngValue]="2">Plate</option><option [ngValue]="3">Descendante</option></select></label>
            <label>Vaisseaux majeurs <small>ca · 0 à 3</small><select formControlName="ca"><option [ngValue]="null">Inconnu</option><option [ngValue]="0">0</option><option [ngValue]="1">1</option><option [ngValue]="2">2</option><option [ngValue]="3">3</option></select></label>
            <label>Résultat thal<select formControlName="thal"><option [ngValue]="null">Inconnu</option><option [ngValue]="3">Normal</option><option [ngValue]="6">Défaut fixe</option><option [ngValue]="7">Défaut réversible</option></select></label>
          </div>
        </div>
        <div class="form-actions"><span>Simulation locale avec les valeurs du formulaire ; n’utilise pas de données réelles.</span><button type="submit" [disabled]="form.invalid || loading || !health?.model_loaded">{{ loading ? 'Simulation…' : 'Lancer la simulation' }} <b>→</b></button></div>
      </form>

      @if (result) {
        <section class="result-panel"><div class="result-top"><div><p class="eyebrow">SORTIE EXPÉRIMENTALE</p><h2>Résultat du modèle</h2></div><span class="version-chip">MLFLOW · V{{ result.model_version }}</span></div>
          <div class="result-body"><div class="probability"><strong>{{ result.disease_probability | percent:'1.1-1' }}</strong><span>Score expérimental produit à partir du profil fictif saisi.</span></div><div class="result-explain"><div class="progress-track"><span [style.width.%]="result.disease_probability * 100"></span></div><p>{{ result.prediction === 1 ? 'La sortie dépasse le seuil expérimental configuré.' : 'La sortie est sous le seuil expérimental configuré.' }}</p><small>Seuil {{ result.threshold | number:'1.3-3' }} · Classe expérimentale {{ result.prediction }}</small></div></div>
          <p class="result-disclaimer">Ce modèle n’est pas validé cliniquement. Sa sortie ne mesure pas le risque réel d’une personne et ne doit guider aucune décision de santé.</p>
        </section>
      }
      @if (error) { <div class="error-banner">{{ error }}</div> }
    </section>
  `,
})
export class ConsultationComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  health: Health | null = null;
  result: Prediction | null = null;
  loading = false;
  apiError = false;
  error = '';

  readonly form = this.fb.nonNullable.group({
    age: [63, [Validators.required, Validators.min(18), Validators.max(110)]],
    sex: [1], cp: [1],
    trestbps: [145, [Validators.min(60), Validators.max(260)]],
    chol: [233, [Validators.min(80), Validators.max(700)]],
    fbs: [0], restecg: [0],
    thalach: [150, [Validators.min(50), Validators.max(250)]],
    exang: [0], oldpeak: [2.3, [Validators.min(0), Validators.max(10)]],
    slope: [1], ca: [0 as number | null], thal: [3 as number | null],
  });

  constructor() {
    this.api.health().subscribe({ next: value => { this.health = value; this.cdr.markForCheck(); }, error: () => { this.apiError = true; this.cdr.markForCheck(); } });
  }

  submit(): void {
    if (this.form.invalid) return;
    this.runPrediction(this.form.getRawValue() as Patient);
  }

  private runPrediction(patient: Patient): void {
    this.loading = true; this.error = ''; this.result = null;
    this.api.predict(patient).subscribe({
      next: value => { this.result = value; this.loading = false; this.cdr.markForCheck(); },
      error: () => { this.error = "La requête de prédiction a échoué. Vérifie que le modèle champion est chargé."; this.loading = false; this.cdr.markForCheck(); },
    });
  }
}
