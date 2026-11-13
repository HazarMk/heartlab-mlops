import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './auth.service';
import { AudienceService } from './audience.service';
import { AuthPageComponent } from './auth-page.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, AuthPageComponent],
  template: `
    @if (!auth.authenticated()) {
      <app-auth-page />
    } @else {
    <div class="app-shell" [attr.dir]="auth.language() === 'ar' && audience.mode() === 'patient' ? 'rtl' : 'ltr'">
      <aside class="sidebar">
        <a class="brand" routerLink="/portal" aria-label="Heart Lab, accueil">
          <svg class="brand-heart" viewBox="0 0 36 36" aria-hidden="true"><path d="M18 31 5.7 19.2C-2.1 11.5 8.7 1.4 16.1 9l1.9 2 1.9-2c7.4-7.6 18.2 2.5 10.4 10.2L18 31Z" /></svg>
          <span class="brand-copy"><strong>HeartLab</strong></span>
        </a>

        <div class="sidebar-section-label">{{ audience.mode() === 'patient' ? 'ESPACE PATIENT' : audience.mode() === 'doctor' ? 'ESPACE MEDECIN' : audience.mode() === 'admin' ? 'ADMINISTRATION' : 'ESPACE RECHERCHE' }}</div>
        <nav class="nav" aria-label="Navigation principale">
          <a [routerLink]="audience.mode() === 'researcher' ? '/consultation' : '/portal'" routerLinkActive="active">
            <span class="nav-icon">01</span><span>{{ audience.mode() === 'patient' ? 'Mon espace' : audience.mode() === 'doctor' ? 'Mon espace' : audience.mode() === 'admin' ? 'Journal d’audit' : 'Simulation modèle' }}</span><span class="nav-arrow">→</span>
          </a>
          @if (audience.mode() === 'patient' || audience.mode() === 'doctor') {
            <a routerLink="/assistant" routerLinkActive="active"><span class="nav-icon">✦</span><span>Assistant santé</span><span class="nav-arrow">→</span></a>
          }
          @if (audience.mode() === 'researcher') {
            <a routerLink="/evaluation" routerLinkActive="active"><span class="nav-icon">02</span><span>Évaluation du modèle</span><span class="nav-arrow">→</span></a>
            <a routerLink="/monitoring" routerLinkActive="active"><span class="nav-icon">03</span><span>Suivi technique</span><span class="nav-arrow">→</span></a>
            <a routerLink="/research-readiness" routerLinkActive="active"><span class="nav-icon">04</span><span>Préparation recherche</span><span class="nav-arrow">→</span></a>
          }
        </nav>

      </aside>

      <div class="app-main">
        <header class="topbar">
          <div class="topbar-title">
            <span>{{ audience.mode() === 'patient' ? 'ESPACE PATIENT' : audience.mode() === 'doctor' ? 'ESPACE MÉDECIN' : audience.mode() === 'admin' ? 'ADMINISTRATION' : 'ESPACE RECHERCHE' }}</span>
            <strong>Bonjour, {{ auth.userName() }}</strong>
          </div>
          <div class="session-controls">
            <span class="session-user"><i></i> Compte connecté</span>
            <button class="logout-button" type="button" (click)="auth.logout()">Se déconnecter <span>↗</span></button>
          </div>
        </header>

        <main class="content-area">
          @if (auth.error()) {
            <section class="auth-error" role="alert">
              <span class="auth-error-mark">!</span>
              <div>
                <h1>Connexion indisponible</h1>
                <p>{{ auth.error() }}</p>
                <button type="button" (click)="retryAuthentication()">Réessayer</button>
              </div>
            </section>
          } @else {
            <router-outlet />
          }
        </main>

      </div>
    </div>
    }
  `,
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly audience = inject(AudienceService);

  retryAuthentication(): void {
    window.location.reload();
  }
}
