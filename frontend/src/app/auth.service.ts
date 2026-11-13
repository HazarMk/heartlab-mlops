import { Injectable, inject, signal } from '@angular/core';
import { AudienceService } from './audience.service';
import { API_BASE_URL } from './api.service';

const DEMO_MODE = false;

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly demoMode = DEMO_MODE;
  private readonly audience = inject(AudienceService);
  readonly userName = signal('Utilisateur');
  readonly error = signal<string | null>(null);
  readonly canEditResearch = signal(false);
  readonly authenticated = signal(false);
  readonly busy = signal(false);
  readonly language = signal<'fr' | 'ar'>(localStorage.getItem('heart_language') === 'ar' ? 'ar' : 'fr');

  setLanguage(language: 'fr' | 'ar'): void {
    this.language.set(language);
    localStorage.setItem('heart_language', language);
  }

  async initialize(): Promise<void> {
    if (DEMO_MODE) { this.authenticated.set(true); this.userName.set('Démo locale'); return; }
    const token = localStorage.getItem('heart_access_token');
    const rawUser = localStorage.getItem('heart_user');
    if (!token || !rawUser) return;
    try {
      const user = JSON.parse(rawUser) as { name?: string; role?: string };
      this.userName.set(user.name || 'Patient');
      this.authenticated.set(true);
      this.selectWorkspace(user.role);
      const response = await fetch(`${API_BASE_URL}/portal/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (response.status === 401) { this.clearSession(); return; }
      if (response.ok) {
        const currentUser = await response.json() as { name: string; email: string; sub: string; role: string };
        localStorage.setItem('heart_user', JSON.stringify(currentUser));
        this.userName.set(currentUser.name || 'Patient');
        this.selectWorkspace(currentUser.role);
      }
    } catch { this.clearSession(); }
  }

  async register(displayName: string, email: string, password: string): Promise<void> {
    this.busy.set(true); this.error.set(null);
    try {
      const response = await fetch(`${API_BASE_URL}/portal/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: displayName, email, password }) });
      if (!response.ok) throw new Error(await this.getError(response));
      await this.login(email, password);
    } catch (error) { this.error.set(error instanceof Error ? error.message : 'Inscription impossible.'); }
    finally { this.busy.set(false); }
  }

  async login(email: string, password: string): Promise<void> {
    this.busy.set(true); this.error.set(null);
    try {
      const response = await fetch(`${API_BASE_URL}/portal/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: 'Patient', email, password }) });
      if (!response.ok) throw new Error(await this.getError(response));
      const data = await response.json() as { access_token: string; user: { name: string; email: string; sub: string; role: string } };
      localStorage.setItem('heart_access_token', data.access_token);
      localStorage.setItem('heart_user', JSON.stringify(data.user));
      this.userName.set(data.user.name); this.authenticated.set(true);
      this.selectWorkspace(data.user.role);
    } catch (error) { this.error.set(error instanceof Error ? error.message : 'Connexion impossible.'); }
    finally { this.busy.set(false); }
  }

  private async getError(response: Response): Promise<string> {
    try { return ((await response.json()) as { detail?: string }).detail || 'Une erreur est survenue.'; }
    catch { return 'Une erreur est survenue.'; }
  }

  private selectWorkspace(role?: string): void {
    if (role === 'doctor') this.audience.select('doctor');
    else if (role === 'admin') this.audience.select('admin');
    else if (role === 'researcher') this.audience.select('researcher');
    else this.audience.select('patient');
  }

  private clearSession(): void {
    localStorage.removeItem('heart_access_token'); localStorage.removeItem('heart_user'); this.authenticated.set(false);
  }

  async accessToken(): Promise<string> {
    if (DEMO_MODE) return '';
    const token = localStorage.getItem('heart_access_token');
    if (!token) throw new Error('Connecte-toi pour continuer.');
    return token;
  }

  async logout(): Promise<void> {
    const token = localStorage.getItem('heart_access_token');
    if (token) void fetch(`${API_BASE_URL}/portal/auth/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    this.clearSession(); this.userName.set('Utilisateur');
  }
}
