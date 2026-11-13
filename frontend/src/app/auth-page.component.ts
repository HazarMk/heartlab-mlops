import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-auth-page', standalone: true, imports: [FormsModule],
  template: `
    <main class="auth-page">
      <section class="auth-card">
        <a class="auth-brand" href="/" aria-label="HeartLab accueil"><svg class="brand-heart" viewBox="0 0 36 36" aria-hidden="true"><path d="M18 31 5.7 19.2C-2.1 11.5 8.7 1.4 16.1 9l1.9 2 1.9-2c7.4-7.6 18.2 2.5 10.4 10.2L18 31Z" /></svg><b>HeartLab</b></a>
        <p class="auth-eyebrow">VOTRE ESPACE SANTÉ</p>
        <h1>{{ signup() ? 'Créer votre compte' : 'Bienvenue' }}</h1>
        <p class="auth-intro">{{ signup() ? 'Inscrivez-vous pour accéder à votre espace patient.' : 'Connectez-vous à votre espace patient sécurisé.' }}</p>
        @if (signup()) {
          <label>Nom complet<input [(ngModel)]="name" name="name" autocomplete="name" placeholder="Votre nom" required></label>
        }
        <label>Adresse e-mail<input [(ngModel)]="email" name="email" type="email" autocomplete="email" placeholder="vous@exemple.com" required></label>
        <label>Mot de passe<input [(ngModel)]="password" name="password" type="password" [autocomplete]="signup() ? 'new-password' : 'current-password'" placeholder="10 caractères minimum" required minlength="10"></label>
        @if (auth.error()) { <p class="auth-form-error" role="alert">{{ auth.error() }}</p> }
        <button class="auth-submit" type="button" [disabled]="auth.busy() || !email || !password || (signup() && !name)" (click)="submit()">
          {{ auth.busy() ? 'Patientez…' : signup() ? 'Créer mon compte patient' : 'Se connecter' }}
        </button>
        <p class="auth-switch">{{ signup() ? 'Vous avez déjà un compte ?' : 'Nouveau sur Heart Lab ?' }}
          <button type="button" (click)="toggle()">{{ signup() ? 'Se connecter' : 'Créer un compte' }}</button>
        </p>
        <p class="auth-note">L’accès médecin est attribué par l’administrateur.</p>
      </section>
    </main>
  `,
})
export class AuthPageComponent {
  readonly auth = inject(AuthService);
  readonly signup = signal(false);
  name = ''; email = ''; password = '';
  toggle(): void { this.signup.update(value => !value); this.auth.error.set(null); }
  submit(): void {
    if (this.signup()) void this.auth.register(this.name.trim(), this.email.trim(), this.password);
    else void this.auth.login(this.email.trim(), this.password);
  }
}
