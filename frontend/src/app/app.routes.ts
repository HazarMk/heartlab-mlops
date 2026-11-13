import { Routes } from '@angular/router';
import { ConsultationComponent } from './consultation.component';
import { EvaluationComponent } from './evaluation.component';
import { MonitoringComponent } from './monitoring.component';
import { ResearchReadinessComponent } from './research-readiness.component';
import { PortalHomeComponent } from './portal-home.component';
import { AssistantComponent } from './assistant.component';
import { researcherOnly } from './research.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'portal' },
  { path: 'portal', component: PortalHomeComponent, title: 'Espace patient et médecin | Heart Lab' },
  { path: 'assistant', component: AssistantComponent, title: 'Assistant santé | HeartLab' },
  { path: 'consultation', component: ConsultationComponent, canActivate: [researcherOnly], title: 'Simulation expérimentale | Heart Disease' },
  { path: 'evaluation', component: EvaluationComponent, canActivate: [researcherOnly], title: 'Qualité du modèle | Heart Disease' },
  { path: 'monitoring', component: MonitoringComponent, canActivate: [researcherOnly], title: 'Monitoring | Heart Disease' },
  { path: 'research-readiness', component: ResearchReadinessComponent, canActivate: [researcherOnly], title: 'Préparation recherche | Heart Lab' },
  { path: '**', redirectTo: 'consultation' },
];
