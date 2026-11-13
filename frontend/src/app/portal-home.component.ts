import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, PatientHealthProfile, PortalAppointment, PortalAuditEvent, PortalConsent, PortalProvider, ProviderProfile } from './api.service';
import { AudienceMode, AudienceService } from './audience.service';
import { AuthService } from './auth.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    @if (audience.mode() === 'patient' && (pendingCount > 0 || confirmedCount > 0)) {
      <section class="appointment-alert" role="status"><span class="alert-icon">!</span><div><strong>Suivi de vos rendez-vous</strong><p>{{ pendingCount }} demande(s) en attente · {{ confirmedCount }} rendez-vous confirmé(s).</p></div><button type="button" (click)="patientTab = 'appointments'">Voir mes rendez-vous</button></section>
    }
    @if (audience.mode() === 'doctor' && pendingCount > 0) {
      <section class="appointment-alert" role="status"><span class="alert-icon">!</span><div><strong>{{ pendingCount }} nouvelle(s) demande(s) de rendez-vous</strong><p>Consultez l’onglet Agenda pour confirmer ou refuser les demandes.</p></div></section>
    }
    <section class="portal-welcome">
      <div>
        <p class="eyebrow">HEART LAB <span>/</span> ESPACE SANTÉ</p>
        <h1>{{ audience.mode() === 'patient' ? 'Votre espace patient' : audience.mode() === 'doctor' ? 'Espace professionnel' : 'Espace recherche' }}</h1>
        <p>{{ audience.mode() === 'patient' ? 'Gérez vos demandes de rendez-vous et vos préférences de contact.' : audience.mode() === 'doctor' ? 'Consultez les demandes de rendez-vous et gérez votre agenda.' : 'Les outils de modèle sont séparés des parcours de soins.' }}</p>
      </div>
      <div class="welcome-visual" aria-label="Illustration du cœur dans un scanner médical">
        <span class="scan-ring scan-ring-one"></span><span class="scan-ring scan-ring-two"></span>
        <img src="/heartlab-cardiac-scan.jpeg" alt="Illustration d’un cœur dans un scanner médical" fetchpriority="high">
        <span class="visual-caption"><i></i> HeartLab · Cardiologie</span>
      </div>
    </section>

    @if (auth.demoMode) {
      <section class="audience-switch portal-audience" aria-label="Choisir un espace de démonstration">
        <span>Ouvrir un espace</span>
        <div role="group" aria-label="Espaces disponibles">
          <button type="button" [class.selected]="audience.mode() === 'patient'" (click)="setMode('patient')">Patient</button>
          <button type="button" [class.selected]="audience.mode() === 'doctor'" (click)="setMode('doctor')">Médecin</button>
          <button type="button" [class.selected]="audience.mode() === 'researcher'" (click)="setMode('researcher')">Recherche</button>
        </div>
        <small>Mode de démonstration avec données fictives. En production, l’espace dépend du rôle attribué au compte.</small>
      </section>
    }

    @if (error) { <div class="error-banner" role="alert">{{ error }}</div> }
    @if (audience.mode() === 'patient') {
      <nav class="patient-section-nav" aria-label="Navigation patient">
        <button type="button" [class.active]="patientTab === 'appointments'" (click)="patientTab = 'appointments'">Rendez-vous</button>
        <button type="button" [class.active]="patientTab === 'history'" (click)="patientTab = 'history'">Historique</button>
        <button type="button" [class.active]="patientTab === 'health'" (click)="patientTab = 'health'">Fiche santé</button>
        <button type="button" [class.active]="patientTab === 'preferences'" (click)="patientTab = 'preferences'">Préférences</button>
        <button type="button" [class.active]="patientTab === 'help'" (click)="patientTab = 'help'" lang="ar">معلومات صحية</button>
      </nav>
    }    @if (audience.mode() === 'patient') {
      <div class="portal-grid">
        <ng-container *ngIf="patientTab === 'appointments'">
        <section class="portal-card appointment-card" id="patient-appointments">
          <div class="portal-section-title"><div><p class="eyebrow">AGENDA</p><h2>Mes rendez-vous</h2></div><button class="portal-refresh" type="button" (click)="refresh()" [disabled]="loading">↻ <span>Actualiser</span></button></div>
          <form class="booking-form" (ngSubmit)="bookAppointment()">
            <div class="booking-heading"><span>+</span><div><strong>Nouvelle demande</strong><small>Choisissez un professionnel et un créneau.</small></div></div>
            <label>Professionnel
              <select name="provider" [(ngModel)]="providerSubject" required>
                <option value="" disabled>Choisir un professionnel</option>
                @for (provider of providers; track provider.subject) {
                  <option [value]="provider.subject">{{ provider.display_name }}{{ provider.specialty ? ' · ' + provider.specialty : '' }}</option>
                }
              </select>
            </label>
            @if (selectedProvider) {
              <article class="provider-detail">
                <div class="provider-detail-head">
                  @if (selectedProvider.photo_data) { <img [src]="selectedProvider.photo_data" [alt]="'Photo de ' + selectedProvider.display_name"> }
                  @else { <span class="provider-photo-placeholder">{{ selectedProvider.display_name.slice(0, 1).toUpperCase() }}</span> }
                  <div><strong>{{ selectedProvider.display_name }}</strong><span>{{ selectedProvider.specialty || 'Spécialité non renseignée' }}</span></div>
                </div>
                @if (selectedProvider.qualifications) { <p><b>Formation :</b> {{ selectedProvider.qualifications }}</p> }
                @if (selectedProvider.city || selectedProvider.area) { <p><b>Zone :</b> {{ selectedProvider.area }}{{ selectedProvider.area && selectedProvider.city ? ', ' : '' }}{{ selectedProvider.city }}</p> }
                @if (selectedProvider.address) { <p><b>Adresse :</b> {{ selectedProvider.address }}</p> }
                @if (selectedProvider.phone) { <a class="provider-phone" [href]="'tel:' + selectedProvider.phone">Appeler le cabinet · {{ selectedProvider.phone }}</a> }
                @if (providerMapLink(selectedProvider); as mapLink) { <a class="provider-map" [href]="mapLink" target="_blank" rel="noopener noreferrer">Voir l’emplacement exact sur la carte ↗</a> }
                @if (!selectedProvider.phone) { <small>Le téléphone du cabinet n’est pas encore renseigné.</small> }
              </article>
            }
            <label>Date et heure souhaitées
              <input name="startsAt" type="datetime-local" [min]="minDateTime" [(ngModel)]="startsAt" required>
            </label>
            <label>Téléphone pour vous contacter
              <input name="contactPhone" type="tel" autocomplete="tel" [(ngModel)]="contactPhone" placeholder="+216 …" required>
            </label>
            <p class="field-hint">Votre demande reste en attente jusqu’à sa confirmation par le cabinet.</p>
            <button class="action-button" type="submit" [disabled]="loading || !providers.length || !contactPhone.trim()">Demander un rendez-vous <b>→</b></button>
          </form>
          <div class="portal-list">
            @for (item of upcomingAppointments; track item.id) {
              <article class="appointment-row">
                <div class="appointment-date"><strong>{{ formatDate(item.starts_at).day }}</strong><span>{{ formatDate(item.starts_at).month }}</span></div>
                <div class="appointment-info"><strong>{{ item.clinician }}</strong><span>{{ formatDate(item.starts_at).time }} · {{ statusLabel(item.status) }}</span></div>
                @if (item.status !== 'cancelled') { <button class="text-button" type="button" (click)="cancel(item.id)">Annuler</button> }
              </article>
            } @empty {
              <div class="empty-state"><span>01</span><strong>Aucun rendez-vous</strong><small>Vos demandes apparaîtront ici.</small></div>
            }
          </div>
        </section>
        </ng-container>

        <ng-container *ngIf="patientTab === 'preferences'">
        <section class="portal-card consent-card" id="patient-preferences">
          <div class="portal-section-title"><div><p class="eyebrow">VOS PRÉFÉRENCES</p><h2>Mes choix de partage</h2></div><span class="consent-lock">CONFIDENTIALITÉ</span></div>
          <p class="portal-intro">Vous pouvez modifier ces préférences à tout moment. Elles sont désactivées par défaut.</p>
          @for (consent of consents; track consent.purpose) {
            <label class="consent-row">
              <span><strong>{{ consent.description }}</strong><small>Modifié : {{ formatDate(consent.updated_at).day }} {{ formatDate(consent.updated_at).month }}</small></span>
              <input type="checkbox" [checked]="consent.granted" (change)="toggleConsent(consent, $event)">
            </label>
          }
          <p class="consent-note">Dans cette version, ces préférences sont enregistrées mais ne déclenchent aucun rappel ni partage de document. Être contacté pour une recherche n’autorise pas l’utilisation de données dans une étude.</p>
        </section>
        </ng-container>
      </div>
      <ng-container *ngIf="patientTab === 'history'">
      <section class="portal-card appointment-history-card" id="patient-history">
        <div class="portal-section-title"><div><p class="eyebrow">VOTRE PARCOURS</p><h2>Historique des rendez-vous</h2><p class="portal-intro">Retrouvez les rendez-vous terminés ou annulés.</p></div></div>
        <div class="portal-list">
          @for (item of appointmentHistory; track item.id) {
            <article class="appointment-row"><div class="appointment-date"><strong>{{ formatDate(item.starts_at).day }}</strong><span>{{ formatDate(item.starts_at).month }}</span></div><div class="appointment-info"><strong>{{ item.clinician }}</strong><span>{{ formatDate(item.starts_at).time }} · {{ statusLabel(item.status) }}</span></div></article>
          } @empty {
            <div class="empty-state"><span>01</span><strong>Aucun historique</strong><small>Vos rendez-vous passés ou annulés apparaîtront ici.</small></div>
          }
        </div>
      </section>
      </ng-container>
      <ng-container *ngIf="patientTab === 'health'">
      <section class="portal-card health-profile-card" id="patient-health">
        <div class="portal-section-title"><div><p class="eyebrow">Informations patient</p><h2>Ma fiche santé</h2><p class="portal-intro">Ces informations sont facultatives et vous pouvez les modifier à tout moment.</p></div></div>
        <form class="health-profile-form" (ngSubmit)="saveHealthProfile()">
          <section class="health-panel health-basics-panel">
            <div class="health-panel-heading"><span>01</span><div><h3>Repères personnels</h3><p>Renseignez seulement les informations utiles au suivi.</p></div></div>
            <label class="age-field">Âge
              <input name="age" type="number" min="0" max="120" [(ngModel)]="healthProfile.age" placeholder="Votre âge">
            </label>
          </section>
          <fieldset class="health-panel symptom-field"><legend>02 · Symptômes ressentis</legend>
            <p class="health-panel-hint">Sélectionnez les éléments que vous souhaitez partager.</p>
            <div class="symptom-options">
              @for (symptom of symptomOptions; track symptom.key) {
                <label class="symptom-option"><input type="checkbox" [checked]="healthProfile.symptoms.includes(symptom.key)" (change)="toggleSymptom(symptom.key, $event)"><span>{{ symptom.label }}</span></label>
              }
            </div>
          </fieldset>
          <section class="health-panel health-notes-panel">
            <div class="health-panel-heading"><span>03</span><div><h3>Informations complémentaires</h3><p>Ces champs sont facultatifs.</p></div></div>
            <label>Précisions sur les symptômes
              <textarea name="symptomNotes" rows="3" maxlength="1000" [(ngModel)]="healthProfile.symptom_notes" placeholder="Depuis quand ? À quelle fréquence ?"></textarea>
            </label>
            <label>Traitements actuels déclarés
              <textarea name="medications" rows="3" maxlength="2000" [(ngModel)]="healthProfile.medications" placeholder="Nom du traitement et dose, si vous les connaissez"></textarea>
            </label>
          </section>
          <section class="health-panel cnam-fields" aria-labelledby="cnam-title">
            <div class="health-panel-heading"><span>04</span><div><p class="eyebrow">COUVERTURE</p><h3 id="cnam-title">Ma situation CNAM</h3><p>Informations déclarées, non vérifiées auprès de la CNAM.</p></div></div>
            <label>Affiliation
              <select name="cnamStatus" [(ngModel)]="healthProfile.cnam_status"><option value="unknown">Je ne sais pas</option><option value="yes">Oui</option><option value="no">Non</option></select>
            </label>
            <label>Parcours indiqué
              <select name="cnamPathway" [(ngModel)]="healthProfile.cnam_pathway"><option value="unknown">Je ne sais pas</option><option value="public">Secteur public</option><option value="private">Secteur privé</option><option value="reimbursement">Remboursement</option></select>
            </label>
          </section>
          @if (profileMessage) { <p class="profile-message" role="status">{{ profileMessage }}</p> }
          <p class="profile-safety-note">Formulaire de démonstration : n’entrez pas de données médicales réelles ni de numéro CNAM. Cette fiche ne permet pas d’établir un diagnostic et ne traite pas les urgences.</p>
          <button class="action-button profile-save" type="submit" [disabled]="profileSaving">{{ profileSaving ? 'Enregistrement…' : 'Enregistrer ma fiche' }}</button>
        </form>
      </section>
      </ng-container>
      <ng-container *ngIf="patientTab === 'help'">
      <section class="portal-card arabic-health-guide" id="patient-help" dir="rtl" lang="ar">
        <div class="portal-section-title"><div><p class="eyebrow">معلومات توعوية</p><h2>أسئلة شائعة حول صحة القلب</h2></div></div>
        <p class="arabic-guide-note">هذه معلومات عامة ولا تشخّص حالتك. لا تنتظر رد التطبيق عند ظهور أعراض شديدة أو مفاجئة.</p>
        <details><summary>هل كل ألم في الصدر يعني وجود مشكلة في القلب؟</summary><p>ليس بالضرورة، فقد تكون لألم الصدر أسباب مختلفة. لا يمكن تحديد السبب عبر التطبيق؛ استشر طبيبًا لتقييم حالتك.</p></details>
        <details><summary>متى أطلب المساعدة العاجلة؟</summary><p>إذا ظهر ألم أو ضغط مفاجئ ومستمر في الصدر، أو صاحبه ضيق في التنفس أو تعرّق أو دوار أو غثيان، اطلب المساعدة الطبية الطارئة فورًا.</p></details>
        <details><summary>ماذا أفعل عند الشعور بخفقان القلب؟</summary><p>دوّن وقت حدوث الخفقان ومدته والأعراض المصاحبة، وناقشه مع الطبيب. إذا صاحبه ألم في الصدر أو ضيق شديد في التنفس أو إغماء، اطلب المساعدة العاجلة.</p></details>
        <details><summary>ما المعلومات المفيدة للطبيب؟</summary><p>اذكر متى بدأت الأعراض، وكم تدوم، وما الذي يصاحبها، واكتب أسماء العلاجات التي تتناولها. لا تبدأ دواءً أو توقفه اعتمادًا على هذه الصفحة.</p></details>
        <a class="arabic-guide-source" href="https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack" target="_blank" rel="noopener noreferrer">المصدر: جمعية القلب الأمريكية — علامات التحذير من النوبة القلبية</a>
      </section>
      </ng-container>
    } @else if (audience.mode() === 'doctor') {
      <nav class="patient-section-nav doctor-section-nav" aria-label="Navigation médecin">
        <button type="button" [class.active]="doctorTab === 'agenda'" (click)="doctorTab = 'agenda'">Agenda</button>
        <button type="button" [class.active]="doctorTab === 'patients'" (click)="doctorTab = 'patients'">Patients</button>
        <button type="button" [class.active]="doctorTab === 'history'" (click)="doctorTab = 'history'">Historique</button>
        <button type="button" [class.active]="doctorTab === 'profile'" (click)="doctorTab = 'profile'">Mon profil</button>
      </nav>
      <ng-container *ngIf="doctorTab === 'patients'">
      <section class="portal-card doctor-clients">
        <div class="portal-section-title"><div><p class="eyebrow">Patientèle</p><h2>Mes patients</h2><p class="portal-intro">Les personnes ayant demandé un rendez-vous auprès de votre cabinet.</p></div><button class="portal-refresh" type="button" (click)="copyPatientSignupLink()">{{ inviteCopied ? 'Lien copié' : 'Inviter un patient' }}</button></div>
        <div class="client-list">
          @for (client of patientClients; track client.patient_subject) {
            <article class="client-row"><span class="client-avatar">{{ (client.patient_name || 'P').slice(0, 1).toUpperCase() }}</span><div><strong>{{ client.patient_name || 'Patient' }}</strong><small>{{ appointmentsForPatient(client.patient_subject) }} rendez-vous · dernier créneau {{ formatDate(client.starts_at).day }} {{ formatDate(client.starts_at).month }}</small></div>@if (client.patient_phone) { <a class="text-button" [href]="'tel:' + client.patient_phone">Appeler</a> }<button class="text-button" type="button" (click)="showPatientProfile(client.id)">Ouvrir la fiche</button></article>
          } @empty {
            <div class="client-empty"><strong>Aucun patient pour le moment</strong><span>Partagez le lien d’inscription ; les patients apparaîtront après leur première demande de rendez-vous.</span></div>
          }
        </div>
      </section>
      </ng-container>
      <ng-container *ngIf="doctorTab === 'agenda'">
      <section class="portal-card clinician-agenda" id="doctor-agenda-calendar">
        <div class="portal-section-title"><div><p class="eyebrow">VOTRE AGENDA</p><h2>Calendrier des rendez-vous</h2><p class="portal-intro">Choisissez un jour pour consulter les rendez-vous et traiter les demandes.</p></div><button class="portal-refresh" type="button" (click)="refresh()" [disabled]="loading">↻ <span>Actualiser</span></button></div>
        <div class="calendar-toolbar">
          <button type="button" aria-label="Mois précédent" (click)="moveCalendarMonth(-1)">‹</button>
          <strong>{{ calendarTitle }}</strong>
          <button type="button" aria-label="Mois suivant" (click)="moveCalendarMonth(1)">›</button>
          <button class="calendar-today" type="button" (click)="goToToday()">Aujourd’hui</button>
        </div>
        <div class="calendar-grid" role="grid" aria-label="Calendrier mensuel des rendez-vous">
          @for (weekday of weekdays; track weekday) { <div class="calendar-weekday" role="columnheader">{{ weekday }}</div> }
          @for (cell of calendarCells; track cell.key) {
            <button type="button" role="gridcell" class="calendar-day" [class.outside-month]="!cell.inMonth" [class.calendar-selected]="cell.key === selectedCalendarDate" [class.has-appointments]="cell.count > 0" [attr.aria-pressed]="cell.key === selectedCalendarDate" [attr.aria-label]="cell.accessibleLabel" (click)="selectCalendarDate(cell.key)">
              <span>{{ cell.day }}</span>@if (cell.count > 0) { <small>{{ cell.count }} RDV</small> }
            </button>
          }
        </div>
        <section class="calendar-day-panel">
          <div class="calendar-day-heading"><div><p class="eyebrow">JOUR SÉLECTIONNÉ</p><h3>{{ selectedCalendarLabel }}</h3></div><span>{{ selectedDateAppointments.length }} rendez-vous</span></div>
          <div class="portal-list">
            @for (item of selectedDateAppointments; track item.id) {
              <article class="clinician-appointment calendar-appointment">
                <div class="appointment-time"><strong>{{ formatDate(item.starts_at).time }}</strong><span>{{ item.status === 'requested' ? 'À confirmer' : statusLabel(item.status) }}</span></div>
                <div class="appointment-info"><strong>{{ item.patient_name || 'Patient' }}</strong><small>Référence {{ item.id.slice(0, 8) }}</small></div>
                <button class="text-button" type="button" (click)="showPatientProfile(item.id)">Fiche patient</button>
                @if (item.patient_phone) { <a class="text-button" [href]="'tel:' + item.patient_phone">Appeler {{ item.patient_phone }}</a> }
                @if (item.status === 'requested') {
                  <div class="appointment-actions"><button class="action-button compact" type="button" (click)="updateAppointment(item.id, 'confirmed')">Confirmer</button><button class="text-button" type="button" (click)="updateAppointment(item.id, 'cancelled')">Refuser</button></div>
                }
              </article>
            } @empty {
              <div class="calendar-empty">Aucun rendez-vous ce jour. Les jours avec un rendez-vous sont indiqués dans le calendrier.</div>
            }
          </div>
        </section>
      </section>
      <section class="portal-note"><strong>Accès à la fiche santé</strong><p>Vous voyez uniquement les informations partagées par les patients pour vos rendez-vous.</p></section>
      </ng-container>
      <ng-container *ngIf="doctorTab === 'history'">
      <section class="portal-card clinician-agenda">
        <div class="portal-section-title"><div><p class="eyebrow">SUIVI DU CABINET</p><h2>Historique des rendez-vous</h2><p class="portal-intro">Demandes refusées, annulées ou rendez-vous passés.</p></div></div>
        <div class="portal-list">
          @for (item of appointmentHistory; track item.id) {
            <article class="clinician-appointment"><div class="appointment-date"><strong>{{ formatDate(item.starts_at).day }}</strong><span>{{ formatDate(item.starts_at).month }}</span></div><div class="appointment-info"><strong>{{ item.patient_name || 'Rendez-vous' }}</strong><span>{{ formatDate(item.starts_at).time }} · {{ statusLabel(item.status) }}</span><small>Référence {{ item.id.slice(0, 8) }}</small></div><button class="text-button" type="button" (click)="showPatientProfile(item.id)">Fiche patient</button></article>
          } @empty {
            <div class="empty-state"><span>01</span><strong>Aucun historique</strong><small>Les rendez-vous passés ou annulés apparaîtront ici.</small></div>
          }
        </div>
      </section>
      </ng-container>
      <ng-container *ngIf="doctorTab === 'profile'">
        <section class="portal-card doctor-profile-card">
          <div class="portal-section-title"><div><p class="eyebrow">FICHE PROFESSIONNELLE</p><h2>Mon profil médecin</h2><p class="portal-intro">Ces informations seront visibles par les patients avant leur demande de rendez-vous.</p></div></div>
          <form class="doctor-profile-form" (ngSubmit)="saveProviderProfile()">
            <div class="doctor-photo-field">
              @if (providerProfile.photo_data) { <img class="doctor-photo-preview" [src]="providerProfile.photo_data" alt="Aperçu de la photo de profil"> }
              @else { <span class="doctor-photo-placeholder">{{ auth.userName().slice(0, 1).toUpperCase() }}</span> }
              <div><label for="provider-photo">Photo de profil</label><input id="provider-photo" type="file" accept="image/jpeg,image/png,image/webp" (change)="chooseProviderPhoto($event)"><small>JPG, PNG ou WebP. L’image est réduite avant l’enregistrement.</small>@if (providerPhotoMessage) { <small class="photo-message" role="status">{{ providerPhotoMessage }}</small> }</div>
              @if (providerProfile.photo_data) { <button class="text-button" type="button" (click)="removeProviderPhoto()">Supprimer la photo</button> }
            </div>
            <label>Spécialité<input name="specialty" [(ngModel)]="providerProfile.specialty" placeholder="Ex. Cardiologie" maxlength="120" required></label>
            <label>Formations et qualifications<textarea name="qualifications" [(ngModel)]="providerProfile.qualifications" rows="5" maxlength="3000" placeholder="Diplômes, faculté, spécialisation, années d’expérience…"></textarea></label>
            <label class="doctor-wide-field">Ville et gouvernorat<input name="clinicCity" [(ngModel)]="providerProfile.city" maxlength="120" placeholder="Ex. Gabès, gouvernorat de Gabès"></label>
            <label class="doctor-wide-field">Délégation, quartier ou zone exacte<input name="clinicArea" [(ngModel)]="providerProfile.area" maxlength="160" placeholder="Ex. Beb Bhar"></label>
            <label class="doctor-wide-field">Adresse exacte du cabinet<textarea name="address" [(ngModel)]="providerProfile.address" rows="3" maxlength="300" placeholder="Rue, numéro, immeuble, étage…"></textarea></label>
            <label>Téléphone du cabinet<input name="doctorPhone" type="tel" autocomplete="tel" [(ngModel)]="providerProfile.phone" placeholder="+216 …" maxlength="32"></label>
            <fieldset class="map-coordinate-fields"><legend>Position exacte sur la carte</legend><button class="text-button geolocation-button" type="button" (click)="captureClinicLocation()">Utiliser ma position actuelle</button><label>Latitude<input name="latitude" type="number" step="any" min="-90" max="90" [(ngModel)]="providerProfile.latitude" placeholder="Ex. 33.88"></label><label>Longitude<input name="longitude" type="number" step="any" min="-180" max="180" [(ngModel)]="providerProfile.longitude" placeholder="Ex. 10.10"></label><small>Autorisez la localisation du navigateur depuis le cabinet, ou saisissez les deux coordonnées GPS manuellement.</small>@if (clinicLocationMessage) { <small class="photo-message" role="status">{{ clinicLocationMessage }}</small> }</fieldset>
            @if (providerProfileMessage) { <p class="profile-message" role="status">{{ providerProfileMessage }}</p> }
            <button class="action-button profile-save" type="submit" [disabled]="providerProfileSaving">{{ providerProfileSaving ? 'Enregistrement…' : 'Enregistrer mon profil' }}</button>
          </form>
        </section>
      </ng-container>
      @if (selectedProfileAppointment && doctorTab === 'patients') {
        <section class="portal-card patient-declaration" aria-live="polite">
          @if (profileLoading) { <p>Chargement de la fiche patient…</p> }
          @else if (selectedPatientProfile) {
            <div class="portal-section-title"><div><p class="eyebrow">Déclarations du patient</p><h2>{{ selectedPatientProfile.display_name }}{{ selectedPatientProfile.age !== null ? ', ' + selectedPatientProfile.age + ' ans' : '' }}</h2></div><button class="text-button" type="button" (click)="closePatientProfile()">Fermer</button></div>
            <p><strong>Symptômes :</strong> {{ symptomSummary(selectedPatientProfile.symptoms) }}</p>
            @if (selectedPatientProfile.symptom_notes) { <p><strong>Précisions :</strong> {{ selectedPatientProfile.symptom_notes }}</p> }
            <p><strong>Traitements déclarés :</strong> {{ selectedPatientProfile.medications || 'Non renseignés' }}</p>
            <p><strong>CNAM :</strong> {{ cnamStatusLabel(selectedPatientProfile.cnam_status) }} · {{ cnamPathwayLabel(selectedPatientProfile.cnam_pathway) }}</p>
            <small>Informations déclarées par le patient, non vérifiées.</small>
          }
        </section>
      }
    } @else if (audience.mode() === 'researcher') {
      <section class="portal-card research-island">
        <p class="eyebrow">ESPACE ISOLÉ</p><h2>Outils de recherche</h2>
        <p>Les simulations de modèle, métriques et préparation recherche restent séparées de l’espace patient et de l’agenda médecin.</p>
        <div class="research-links"><a routerLink="/consultation">Simulation expérimentale</a><a routerLink="/evaluation">Évaluation du modèle</a><a routerLink="/monitoring">Métriques techniques</a><a routerLink="/research-readiness">Préparation recherche</a></div>
      </section>
    } @else {
      <section class="portal-card admin-island">
        <div class="portal-section-title"><div><p class="eyebrow">ADMINISTRATION</p><h2>Journal des accès et actions</h2></div><span class="consent-lock">RÔLE ADMIN</span></div>
        <p class="portal-intro">L’espace d’administration ne donne pas accès aux dossiers ni au contenu médical.</p>
        <div class="portal-list">
          @for (event of auditEvents; track $index) {
            <article class="audit-row"><span>{{ event.actor_role }}</span><strong>{{ event.action }} · {{ event.resource }}</strong><small>{{ event.resource_id }} · {{ formatDate(event.occurred_at).day }} {{ formatDate(event.occurred_at).month }} {{ formatDate(event.occurred_at).time }}</small></article>
          } @empty {
            <div class="empty-state"><span>01</span><strong>Aucune activité enregistrée</strong><small>Les accès et modifications apparaîtront ici.</small></div>
          }
        </div>
      </section>
    }
  `,
})
export class PortalHomeComponent {
  readonly audience = inject(AudienceService);
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  providers: PortalProvider[] = [];
  appointments: PortalAppointment[] = [];
  consents: PortalConsent[] = [];
  auditEvents: PortalAuditEvent[] = [];
  healthProfile: PatientHealthProfile = { display_name: '', age: null, symptoms: [], symptom_notes: '', medications: '', cnam_status: 'unknown', cnam_pathway: 'unknown', updated_at: null };
  readonly symptomOptions = [
    { key: 'chest_pain', label: 'Douleur thoracique' },
    { key: 'shortness_of_breath', label: 'Essoufflement' },
    { key: 'palpitations', label: 'Palpitations' },
    { key: 'fatigue', label: 'Fatigue' },
    { key: 'dizziness', label: 'Étourdissements' },
    { key: 'other', label: 'Autre' },
  ];
  readonly weekdays = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
  calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  selectedCalendarDate = this.dateKey(new Date());
  profileSaving = false;
  profileLoading = false;
  profileMessage = '';
  selectedProfileAppointment = '';
  selectedPatientProfile: PatientHealthProfile | null = null;
  inviteCopied = false;
  providerSubject = '';
  contactPhone = '';
  providerProfile: ProviderProfile = { specialty: '', qualifications: '', address: '', city: '', area: '', phone: '', latitude: null, longitude: null, photo_data: null };
  providerProfileSaving = false;
  providerProfileMessage = '';
  providerPhotoMessage = '';
  clinicLocationMessage = '';
  startsAt = '';
  loading = false;
  error = '';
  patientTab: 'appointments' | 'history' | 'health' | 'preferences' | 'help' = 'appointments';
  doctorTab: 'agenda' | 'patients' | 'history' | 'profile' = 'agenda';

  constructor() { this.refresh(); }

  get minDateTime(): string {
    const date = new Date(Date.now() + 60 * 60 * 1000);
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  }

  get pendingCount(): number { return this.appointments.filter(item => item.status === 'requested').length; }
  get confirmedCount(): number { return this.appointments.filter(item => item.status === 'confirmed').length; }
  get appointmentHistory(): PortalAppointment[] { return this.appointments.filter(item => item.status === 'cancelled' || new Date(item.starts_at).getTime() < Date.now()); }
  get upcomingAppointments(): PortalAppointment[] { return this.appointments.filter(item => item.status !== 'cancelled' && new Date(item.starts_at).getTime() >= Date.now()); }
  get selectedProvider(): PortalProvider | undefined { return this.providers.find(provider => provider.subject === this.providerSubject); }
  get calendarTitle(): string { return new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' }).format(this.calendarMonth); }
  get selectedCalendarLabel(): string {
    const [year, month, day] = this.selectedCalendarDate.split('-').map(Number);
    return new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(year, month - 1, day));
  }
  get calendarCells(): Array<{key: string; day: number; inMonth: boolean; count: number; accessibleLabel: string}> {
    const firstDay = new Date(this.calendarMonth.getFullYear(), this.calendarMonth.getMonth(), 1);
    const start = new Date(firstDay);
    start.setDate(firstDay.getDate() - ((firstDay.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      const key = this.dateKey(date);
      const count = this.appointments.filter(item => item.status !== 'cancelled' && this.dateKey(item.starts_at) === key).length;
      const label = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' }).format(date);
      return { key, day: date.getDate(), inMonth: date.getMonth() === this.calendarMonth.getMonth(), count, accessibleLabel: `${label}${count ? `, ${count} rendez-vous` : ''}` };
    });
  }
  get selectedDateAppointments(): PortalAppointment[] {
    return this.appointments
      .filter(item => item.status !== 'cancelled' && this.dateKey(item.starts_at) === this.selectedCalendarDate)
      .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
  }

  private dateKey(value: string | Date): string {
    const date = value instanceof Date ? value : new Date(value);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  selectCalendarDate(key: string): void {
    this.selectedCalendarDate = key;
    const [year, month] = key.split('-').map(Number);
    this.calendarMonth = new Date(year, month - 1, 1);
  }

  moveCalendarMonth(offset: number): void {
    this.calendarMonth = new Date(this.calendarMonth.getFullYear(), this.calendarMonth.getMonth() + offset, 1);
    this.selectedCalendarDate = this.dateKey(this.calendarMonth);
  }

  goToToday(): void {
    const today = new Date();
    this.calendarMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    this.selectedCalendarDate = this.dateKey(today);
  }

  providerMapLink(provider: PortalProvider): string | null {
    if (provider.latitude != null && provider.longitude != null) {
      return `https://www.google.com/maps/search/?api=1&query=${provider.latitude},${provider.longitude}`;
    }
    const query = [provider.address, provider.area, provider.city].filter(Boolean).join(', ');
    return query ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}` : null;
  }

  captureClinicLocation(): void {
    this.clinicLocationMessage = '';
    if (!navigator.geolocation) {
      this.clinicLocationMessage = 'La géolocalisation n’est pas disponible sur cet appareil.';
      return;
    }
    navigator.geolocation.getCurrentPosition(
      position => {
        this.providerProfile.latitude = Number(position.coords.latitude.toFixed(6));
        this.providerProfile.longitude = Number(position.coords.longitude.toFixed(6));
        this.clinicLocationMessage = 'Position GPS ajoutée. Enregistrez le profil pour la publier.';
        this.cdr.markForCheck();
      },
      () => {
        this.clinicLocationMessage = 'Position non obtenue. Autorisez la localisation ou saisissez les coordonnées GPS.';
        this.cdr.markForCheck();
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  chooseProviderPhoto(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    this.providerPhotoMessage = '';
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      this.providerPhotoMessage = 'Choisissez une image JPG, PNG ou WebP de moins de 10 Mo.';
      input.value = '';
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      const maxSide = 480;
      const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      const context = canvas.getContext('2d');
      URL.revokeObjectURL(objectUrl);
      if (!context) {
        this.providerPhotoMessage = 'Impossible de traiter cette image.';
      } else {
        context.fillStyle = '#edf6ff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const compressed = canvas.toDataURL('image/jpeg', 0.78);
        if (compressed.length > 390_000) this.providerPhotoMessage = 'Cette photo reste trop volumineuse. Choisissez une image plus petite.';
        else { this.providerProfile.photo_data = compressed; this.providerPhotoMessage = 'Photo prête. Enregistrez votre profil pour la publier.'; }
      }
      input.value = '';
      this.cdr.markForCheck();
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      this.providerPhotoMessage = 'Impossible de lire cette image.';
      input.value = '';
      this.cdr.markForCheck();
    };
    image.src = objectUrl;
  }

  removeProviderPhoto(): void {
    this.providerProfile.photo_data = null;
    this.providerPhotoMessage = 'La photo sera retirée après l’enregistrement du profil.';
  }
  get patientClients(): PortalAppointment[] {
    const seen = new Set<string>();
    return this.appointments.filter(item => {
      if (!item.patient_subject || seen.has(item.patient_subject)) return false;
      seen.add(item.patient_subject);
      return true;
    });
  }
  appointmentsForPatient(subject?: string): number { return this.appointments.filter(item => item.patient_subject === subject).length; }

  async copyPatientSignupLink(): Promise<void> {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/`);
      this.inviteCopied = true;
      window.setTimeout(() => { this.inviteCopied = false; this.cdr.markForCheck(); }, 2500);
    } catch { this.error = 'Impossible de copier le lien. Copiez l’adresse affichée dans le navigateur.'; }
  }

  setMode(mode: AudienceMode): void {
    this.audience.select(mode);
    this.error = '';
    this.appointments = [];
    this.consents = [];
    this.refresh();
  }

  refresh(): void {
    this.loading = true;
    this.error = '';
    const mode = this.audience.mode();
    if (mode === 'patient') this.loadAppointments();
    if (mode === 'doctor') {
      this.api.registerProviderMe().subscribe({
        next: provider => {
          this.providerProfile = {
            specialty: provider.specialty ?? '', qualifications: provider.qualifications ?? '',
            address: provider.address ?? '', city: provider.city ?? '', area: provider.area ?? '', phone: provider.phone ?? '',
            latitude: provider.latitude ?? null, longitude: provider.longitude ?? null,
            photo_data: provider.photo_data ?? null,
          };
          this.loadAppointments();
        },
        error: () => { this.error = 'Votre espace professionnel n’est pas encore configuré.'; this.loading = false; this.cdr.markForCheck(); },
      });
    }
    if (mode === 'patient') {
      this.loadHealthProfile();
      this.api.providers().subscribe({ next: value => { this.providers = value; this.providerSubject ||= value[0]?.subject ?? ''; this.cdr.markForCheck(); }, error: () => { this.error = 'La liste des professionnels est indisponible.'; this.cdr.markForCheck(); } });
      this.api.consents().subscribe({ next: value => { this.consents = value; this.cdr.markForCheck(); }, error: () => { this.error = 'Impossible de charger vos préférences.'; this.cdr.markForCheck(); } });
    }
    if (mode === 'admin') {
      this.api.audit().subscribe({ next: value => { this.auditEvents = value; this.loading = false; this.cdr.markForCheck(); }, error: () => { this.error = 'Journal réservé aux comptes administrateurs indisponible.'; this.loading = false; this.cdr.markForCheck(); } });
    }
    if (mode === 'researcher') this.loading = false;
  }

  saveProviderProfile(): void {
    this.providerProfileSaving = true;
    this.providerProfileMessage = '';
    this.api.updateProviderProfile(this.providerProfile).subscribe({
      next: value => {
        this.providerProfile = { specialty: value.specialty, qualifications: value.qualifications, address: value.address, city: value.city, area: value.area, phone: value.phone, latitude: value.latitude, longitude: value.longitude, photo_data: value.photo_data };
        this.providerProfileMessage = 'Votre profil professionnel a été enregistré.';
        this.providerProfileSaving = false;
        this.refresh();
      },
      error: () => { this.providerProfileMessage = 'Enregistrement impossible. Vérifiez les coordonnées GPS et réessayez.'; this.providerProfileSaving = false; this.cdr.markForCheck(); },
    });
  }

  private loadAppointments(): void {
    this.api.appointments().subscribe({
      next: value => {
        this.appointments = value;
        if (this.audience.mode() === 'doctor') {
          const next = value.filter(item => item.status !== 'cancelled' && new Date(item.starts_at).getTime() >= Date.now()).sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0];
          if (next) this.selectCalendarDate(this.dateKey(next.starts_at));
        }
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => { this.error = 'Impossible de charger votre agenda.'; this.loading = false; this.cdr.markForCheck(); },
    });
  }

  private loadHealthProfile(): void {
    this.api.patientProfile().subscribe({
      next: profile => { this.healthProfile = profile; this.cdr.markForCheck(); },
      error: () => { this.profileMessage = 'Impossible de charger votre fiche.'; this.cdr.markForCheck(); },
    });
  }

  toggleSymptom(key: string, event: Event): void {
    const selected = (event.target as HTMLInputElement).checked;
    this.healthProfile.symptoms = selected
      ? [...new Set([...this.healthProfile.symptoms, key])]
      : this.healthProfile.symptoms.filter(value => value !== key);
  }

  saveHealthProfile(): void {
    this.profileSaving = true;
    this.profileMessage = '';
    const { age, symptoms, symptom_notes, medications, cnam_status, cnam_pathway } = this.healthProfile;
    this.api.savePatientProfile({ age, symptoms, symptom_notes, medications, cnam_status, cnam_pathway }).subscribe({
      next: result => { this.healthProfile.updated_at = result.updated_at; this.profileMessage = 'Votre fiche a été enregistrée.'; this.profileSaving = false; this.cdr.markForCheck(); },
      error: () => { this.profileMessage = 'L’enregistrement a échoué. Réessayez.'; this.profileSaving = false; this.cdr.markForCheck(); },
    });
  }

  showPatientProfile(appointmentId: string): void {
    this.doctorTab = 'patients';
    this.selectedProfileAppointment = appointmentId;
    this.selectedPatientProfile = null;
    this.profileLoading = true;
    this.api.appointmentPatientProfile(appointmentId).subscribe({
      next: profile => { this.selectedPatientProfile = profile; this.profileLoading = false; this.cdr.markForCheck(); },
      error: () => { this.error = 'La fiche patient est accessible uniquement pour un rendez-vous qui vous est attribué.'; this.profileLoading = false; this.selectedProfileAppointment = ''; this.cdr.markForCheck(); },
    });
  }

  closePatientProfile(): void { this.selectedProfileAppointment = ''; this.selectedPatientProfile = null; }

  symptomSummary(values: string[]): string {
    if (!values.length) return 'Non renseignés';
    return values.map(value => this.symptomOptions.find(option => option.key === value)?.label ?? value).join(', ');
  }

  cnamStatusLabel(value: PatientHealthProfile['cnam_status']): string {
    return value === 'yes' ? 'Affiliation déclarée' : value === 'no' ? 'Aucune affiliation déclarée' : 'Non précisé';
  }

  cnamPathwayLabel(value: PatientHealthProfile['cnam_pathway']): string {
    return value === 'public' ? 'Secteur public' : value === 'private' ? 'Secteur privé' : value === 'reimbursement' ? 'Remboursement' : 'Parcours non précisé';
  }

  bookAppointment(): void {
    const selected = new Date(this.startsAt);
    if (!this.providerSubject || !this.startsAt || Number.isNaN(selected.getTime()) || selected <= new Date()) {
      this.error = 'Choisissez un professionnel et une date future.';
      return;
    }
    this.loading = true;
    this.api.requestAppointment(this.providerSubject, selected.toISOString(), this.contactPhone.trim()).subscribe({
      next: () => { this.startsAt = ''; this.refresh(); },
      error: () => { this.error = 'Ce créneau est indisponible ou la demande n’a pas abouti.'; this.loading = false; this.cdr.markForCheck(); },
    });
  }

  cancel(id: string): void {
    this.api.cancelAppointment(id).subscribe({ next: () => this.refresh(), error: () => { this.error = 'Annulation impossible pour ce rendez-vous.'; this.cdr.markForCheck(); } });
  }

  updateAppointment(id: string, status: 'confirmed' | 'cancelled'): void {
    this.api.updateAppointment(id, status).subscribe({ next: () => this.refresh(), error: () => { this.error = 'La demande a déjà été traitée ou ne vous est pas attribuée.'; this.cdr.markForCheck(); } });
  }

  toggleConsent(consent: PortalConsent, event: Event): void {
    const granted = (event.target as HTMLInputElement).checked;
    this.api.updateConsent(consent.purpose, granted).subscribe({
      next: () => { consent.granted = granted; consent.updated_at = new Date().toISOString(); this.cdr.markForCheck(); },
      error: () => { this.error = 'Votre préférence n’a pas pu être enregistrée.'; this.cdr.markForCheck(); },
    });
  }

  formatDate(value: string): { day: string; month: string; time: string } {
    const date = new Date(value);
    return {
      day: new Intl.DateTimeFormat('fr-FR', { day: '2-digit' }).format(date),
      month: new Intl.DateTimeFormat('fr-FR', { month: 'short' }).format(date).replace('.', ''),
      time: new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(date),
    };
  }

  statusLabel(status: PortalAppointment['status']): string {
    return status === 'requested' ? 'En attente' : status === 'confirmed' ? 'Confirmé' : 'Annulé';
  }
}
