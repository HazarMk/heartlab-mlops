import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timeout } from 'rxjs';

export const API_BASE_URL = 'http://127.0.0.1:8001';

export interface Patient {
  age: number; sex: number; cp: number; trestbps: number; chol: number;
  fbs: number; restecg: number; thalach: number; exang: number;
  oldpeak: number; slope: number; ca: number | null; thal: number | null;
}

export interface Health {
  status: string; model_loaded: boolean; model_name: string;
  model_version: string | null; decision_threshold: number;
}

export interface Prediction {
  disease_probability: number; prediction: number; decision: string;
  threshold: number; model_version: string;
}

export interface Evaluation {
  accuracy: number; precision: number; recall: number; rows: number;
}

export interface PortalProvider {
  subject: string; display_name: string; specialty?: string; qualifications?: string;
  address?: string; city?: string; area?: string; phone?: string; latitude?: number | null; longitude?: number | null; photo_data?: string | null;
}
export interface ProviderProfile {
  specialty: string; qualifications: string; address: string; city: string; area: string; phone: string;
  latitude: number | null; longitude: number | null; photo_data: string | null;
}
export interface PortalAppointment {
  id: string; starts_at: string; status: 'requested' | 'confirmed' | 'cancelled'; clinician: string;
  patient_subject?: string; patient_name?: string; patient_phone?: string;
}
export interface PortalConsent {
  purpose: string; granted: boolean; updated_at: string; description: string;
}
export interface PatientHealthProfile {
  display_name: string; age: number | null; symptoms: string[]; symptom_notes: string;
  medications: string; cnam_status: 'unknown' | 'yes' | 'no';
  cnam_pathway: 'unknown' | 'public' | 'private' | 'reimbursement'; updated_at: string | null;
}
export interface PortalAuditEvent {
  actor_subject: string; actor_role: string; action: string;
  resource: string; resource_id: string; occurred_at: string;
}

export interface AssistantStatus { llm_enabled: boolean; model_ready: boolean; provider: 'huggingface_local' | 'openai'; model: string; source_count: number; mode: 'rag_llm' | 'rag_only'; }
export interface AssistantSource { id: string; title: string; source: string; url: string | null; }
export interface AssistantReply { answer: string; mode: 'rag_llm' | 'rag_only' | 'rag_no_match' | 'rag_fallback'; llm_enabled: boolean; sources: AssistantSource[]; notice?: string | null; }

export interface ResearchReadinessItem {
  id: string;
  title: string;
  description: string;
  status: 'not_started' | 'in_progress' | 'blocked' | 'complete';
  owner: string | null;
  due_date: string | null;
  notes: string | null;
  updated_at: string | null;
  updated_by: string | null;
  history: ResearchReadinessAuditEvent[];
  evidence: string;
}

export interface ResearchReadinessAuditEvent {
  changed_fields: string[];
  updated_at: string;
  updated_by: string;
}

export interface ResearchReadinessUpdate {
  status?: ResearchReadinessItem['status'];
  owner?: string | null;
  due_date?: string | null;
  notes?: string | null;
}

export interface ResearchReadiness {
  project_stage: string;
  region: string;
  clinical_use_enabled: boolean;
  model_status: string;
  completed_items: number;
  total_items: number;
  disclaimer: string;
  items: ResearchReadinessItem[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  health(): Observable<Health> { return this.http.get<Health>(`${this.baseUrl}/health`); }
  assistantStatus(): Observable<AssistantStatus> { return this.http.get<AssistantStatus>(`${this.baseUrl}/assistant/status`); }
  askAssistant(question: string, use_llm: boolean): Observable<AssistantReply> {
    return this.http.post<AssistantReply>(`${this.baseUrl}/assistant/chat`, { question, use_llm }).pipe(timeout({ first: 25000 }));
  }
  metrics(): Observable<string> { return this.http.get(`${this.baseUrl}/metrics/`, { responseType: 'text' }); }
  predict(patient: Patient): Observable<Prediction> { return this.http.post<Prediction>(`${this.baseUrl}/predict`, patient); }
  evaluate(patients: Patient[], labels: number[]): Observable<Evaluation> {
    return this.http.post<Evaluation>(`${this.baseUrl}/evaluate`, { patients, labels });
  }
  researchReadiness(): Observable<ResearchReadiness> {
    return this.http.get<ResearchReadiness>(`${this.baseUrl}/research/readiness`);
  }
  updateResearchReadinessItem(
    itemId: string,
    update: ResearchReadinessUpdate,
  ): Observable<ResearchReadinessItem> {
    return this.http.put<ResearchReadinessItem>(
      `${this.baseUrl}/research/readiness/${encodeURIComponent(itemId)}`,
      update,
    );
  }
  providers(): Observable<PortalProvider[]> { return this.http.get<PortalProvider[]>(`${this.baseUrl}/portal/providers`); }
  registerProviderMe(): Observable<PortalProvider & {active: boolean}> {
    return this.http.post<PortalProvider & {active: boolean}>(`${this.baseUrl}/portal/providers/me`, {});
  }
  updateProviderProfile(profile: ProviderProfile): Observable<{saved: boolean} & ProviderProfile> {
    return this.http.put<{saved: boolean} & ProviderProfile>(`${this.baseUrl}/portal/providers/me`, profile);
  }
  audit(limit = 100): Observable<PortalAuditEvent[]> {
    return this.http.get<PortalAuditEvent[]>(`${this.baseUrl}/portal/audit`, { params: { limit } });
  }
  appointments(): Observable<PortalAppointment[]> { return this.http.get<PortalAppointment[]>(`${this.baseUrl}/portal/appointments`); }
  requestAppointment(provider_subject: string, starts_at: string, contact_phone: string): Observable<{id: string; status: string}> {
    return this.http.post<{id: string; status: string}>(`${this.baseUrl}/portal/appointments`, { provider_subject, starts_at, contact_phone });
  }
  updateAppointment(id: string, status: 'confirmed' | 'cancelled'): Observable<{id: string; status: string}> {
    return this.http.patch<{id: string; status: string}>(`${this.baseUrl}/portal/appointments/${encodeURIComponent(id)}`, { status });
  }
  cancelAppointment(id: string): Observable<{id: string; status: string}> {
    return this.http.delete<{id: string; status: string}>(`${this.baseUrl}/portal/appointments/${encodeURIComponent(id)}`);
  }
  consents(): Observable<PortalConsent[]> { return this.http.get<PortalConsent[]>(`${this.baseUrl}/portal/consents`); }
  updateConsent(purpose: string, granted: boolean): Observable<{purpose: string; granted: boolean; updated_at: string}> {
    return this.http.put<{purpose: string; granted: boolean; updated_at: string}>(
      `${this.baseUrl}/portal/consents/${encodeURIComponent(purpose)}`, { granted },
    );
  }
  patientProfile(): Observable<PatientHealthProfile> { return this.http.get<PatientHealthProfile>(`${this.baseUrl}/portal/profile`); }
  savePatientProfile(profile: Omit<PatientHealthProfile, 'display_name' | 'updated_at'>): Observable<{saved: boolean; updated_at: string}> {
    return this.http.put<{saved: boolean; updated_at: string}>(`${this.baseUrl}/portal/profile`, profile);
  }
  appointmentPatientProfile(id: string): Observable<PatientHealthProfile> {
    return this.http.get<PatientHealthProfile>(`${this.baseUrl}/portal/appointments/${encodeURIComponent(id)}/patient-profile`);
  }
}
