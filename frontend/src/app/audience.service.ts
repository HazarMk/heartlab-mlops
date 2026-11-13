import { Injectable, signal } from '@angular/core';

export type AudienceMode = 'admin' | 'doctor' | 'patient' | 'researcher';

@Injectable({ providedIn: 'root' })
export class AudienceService {
  readonly mode = signal<AudienceMode>('patient');

  select(mode: AudienceMode): void {
    this.mode.set(mode);
  }
}
